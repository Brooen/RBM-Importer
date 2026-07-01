import os
from mathutils import Matrix
import hashlib
import struct
import tempfile

from io_import_rbm.io import stream


# Function to decompress normal/tangent data
def decompress_normal(hex_value):
    f = stream.hex_to_float(hex_value)
    x = ((f / 1.0) % 1.0) * 2.0 - 1.0
    y = ((f / 256.0) % 1.0) * 2.0 - 1.0
    z = ((f / 65536.0) % 1.0) * 2.0 - 1.0
    w = 1.0 if f >= 0 else -1.0
    return x, y, z, w


# Function to remove `_lod#` from filename
def clean_filename(filename):
    return filename.split('_lod')[0]


# Function to remove `_dif` from the end and strip file extension
def clean_material_name(filepath):
    base_name = os.path.splitext(filepath)[0]
    return base_name.replace('_dif', '')


# Function to process R16G16B16_SNORM format
def process_r16g16b16_snorm(file):
    r = stream.read_s16(file) / 32767.0
    g = stream.read_s16(file) / 32767.0
    b = stream.read_s16(file) / 32767.0
    return r, g, b


# Function to process R16G16_UNORM format
def process_r16g16_unorm(file):
    r = stream.read_u16(file) / 65535.0
    g = stream.read_u16(file) / -65535.0
    return r, g


# Function to transform UVs
def transform_uvs(uvs, uv_extent):
    transformed_uvs = []
    u_extent, v_extent = uv_extent

    for u, v in uvs:
        # Step 1: Move by (-0.5, 0.5)
        u -= 0.5
        v += 0.5

        # Step 2: Add 1 to any negative u or v values
        if u < 0: u += 1
        if v < 0: v += 1

        # Step 3: Scale by UV extent
        u *= u_extent
        v *= v_extent

        # Step 4: Move by (-u_extent/2, v_extent/2)
        u -= u_extent / 2
        v -= v_extent / 2

        # Step 5: Scale by 2
        u *= 2
        v *= 2

        transformed_uvs.append((u, v))

    return transformed_uvs

# Function to staticly transform UVs
def scale_uvs(uvs):
    scaled_uvs = []

    for u, v in uvs:

        # Scale by 2
        u *= 2
        v *= 2

        scaled_uvs.append((u, v))

    return scaled_uvs


# Function to apply matrix transforms
def apply_transformations(obj, matrix_values):
    """
    game world matrix is y-up, right-handed, row-major
    """

    y_up_to_z_up = Matrix((
        (1, 0, 0, 0),
        (0, 0, -1, 0),  # Z becomes -Y
        (0, 1, 0, 0),  # Y becomes Z
        (0, 0, 0, 1),
    ))

    try:
        if isinstance(matrix_values, Matrix):
            game_matrix = matrix_values
        else:
            game_matrix = Matrix((
                matrix_values[0:4],
                matrix_values[4:8],
                matrix_values[8:12],
                matrix_values[12:16]
            ))

        blender_matrix = game_matrix
        # Convert to Blender's column-major format
        blender_matrix = game_matrix.transposed()

        # Change basis from Y-up to Z-up
        blender_matrix = y_up_to_z_up @ blender_matrix

        if obj.parent is not None:
            blender_matrix = obj.parent.matrix_world @ blender_matrix

            # Rotate the child by -90° around the X-axis
            x_minus_90_rotation = Matrix.Rotation(-1.5708, 4, 'X')  # -90° in radians
            blender_matrix = blender_matrix @ x_minus_90_rotation

        obj.matrix_world = blender_matrix

    except Exception as e:
        print(f"Error applying transformation: {e}"
              f"\nto matrix {matrix_values}")


# Calculate the hash of the rest of the paths and renderblocktype
def hash_paths_and_type(filepaths, renderblocktype):
    hasher = hashlib.sha256()
    # Combine all filepaths except the first and renderblocktype into a single string
    combined_data = ''.join(filepaths[1:]) + str(renderblocktype)
    hasher.update(combined_data.encode('utf-8'))
    return hasher.hexdigest()[:8]  # Shorten hash for readability

# Function to load the ddsc.db mapping
def load_ddsc_flags(ddsc_db_path):
    ddsc_flags = {}
    try:
        with open(ddsc_db_path, 'rb') as f:
            while True:
                # Read until the first ASCII space (end of file path)
                filepath_bytes = bytearray()
                while (byte := f.read(1)) != b' ':
                    if not byte:  # EOF
                        return ddsc_flags
                    filepath_bytes.extend(byte)

                # Decode the file path as ASCII
                filepath = filepath_bytes.decode('ascii')

                # Read the flag as 16-bit little-endian
                flag_bytes = f.read(2)
                if len(flag_bytes) < 2:  # EOF or corrupted data
                    break
                flag = int.from_bytes(flag_bytes, byteorder='little')

                # Skip the following ASCII space after the flag
                space = f.read(1)
                if space != b' ':
                    print(f"Unexpected character after flag: {space}")
                    break

                # Store the path and flag in the dictionary
                ddsc_flags[filepath] = flag
    except FileNotFoundError:
        print(f"Error: ddsc.db file not found at {ddsc_db_path}")
    except Exception as e:
        print(f"Error reading ddsc.db: {e}")
    return ddsc_flags


# ===========================================================================
#  DDSC (Avalanche 'AVTX') -> DDS conversion  (Just Cause 3)
# ===========================================================================
# A JC3 .ddsc is a block-compressed texture wrapped in a small 'AVTX' header
# plus an element table; the single high-resolution mip usually lives in a
# sibling .hmddsc stream. Blender can't read a .ddsc directly, so when the
# chosen texture extension is ".ddsc" we reassemble the mip chain, prepend a
# normal DDS header, and hand Blender the resulting .dds.
#
# This is a pure-Python port of the JC3 path of AVTeX (JustCause.Textures.Core:
# AvtxTexture.Parse + AvtxExport.ExportLegacy / WriteLegacyDds), producing the
# same on-disk .dds the JC3 ConvertTexture tool does.

_AVTX_MAGIC = b"AVTX"
_AVTX_CUBEMAP_FLAG = 0x40


class _AvtxTexture(object):
    __slots__ = ("fmt", "width", "height", "depth", "flags", "mip_count", "elements")


def _avtx_parse(data):
    """Parse a JC3 AVTX header at the start of the .ddsc. Returns _AvtxTexture
    or None. Little-endian (JC3 PC)."""
    if data is None or len(data) < 128 or data[0:4] != _AVTX_MAGIC:
        return None

    t = _AvtxTexture()
    (t.fmt,) = struct.unpack_from("<I", data, 8)
    (t.width, t.height, t.depth, t.flags) = struct.unpack_from("<HHHH", data, 12)
    t.mip_count = data[20]

    t.elements = []
    ep = 32
    for _ in range(8):                       # 8 elements, 12 bytes each
        offset, size = struct.unpack_from("<II", data, ep)
        external = data[ep + 11] != 0        # 0 = inline (.ddsc), else .hmddsc
        t.elements.append({"offset": offset, "size": size, "is_external": external})
        ep += 12
    return t


# ---- DDS pixel format (JC3 ConvertTexture GetPixelFormat) ------------------
_FOURCC_DXT1, _FOURCC_DXT3, _FOURCC_DXT5, _FOURCC_DX10 = (
    0x31545844, 0x33545844, 0x35545844, 0x30315844)


def _jc3_pixelformat(dxgi):
    """Mirror of the JC3 exporter: legacy FourCC for the four common formats,
    the DX10 extension for R8/BC4/BC5/BC7. Raises for anything else (the JC3
    packers don't accept other formats)."""
    # (flags, fourcc, rgb_bits, r, g, b, a, use_dx10)
    if dxgi == 71:                                   # BC1  -> DXT1
        return (0x4, _FOURCC_DXT1, 0, 0, 0, 0, 0, False)
    if dxgi == 74:                                   # BC2  -> DXT3
        return (0x4, _FOURCC_DXT3, 0, 0, 0, 0, 0, False)
    if dxgi == 77:                                   # BC3  -> DXT5
        return (0x4, _FOURCC_DXT5, 0, 0, 0, 0, 0, False)
    if dxgi == 87:                                   # B8G8R8A8 -> A8R8G8B8
        return (0x41, 0, 32,
                0x00FF0000, 0x0000FF00, 0x000000FF, 0xFF000000, False)
    if dxgi in (61, 80, 83, 98):                     # R8 / BC4 / BC5 / BC7
        return (0x4, _FOURCC_DX10, 0, 0, 0, 0, 0, True)
    raise ValueError("JC3 does not support DXGI format %d." % dxgi)


def _write_jc3_dds_header(dxgi, width, height, depth, mipcount):
    """Squish-style DDS header, matching AVTeX WriteLegacyDds byte layout."""
    flags, fourcc, rgb_bits, rmask, gmask, bmask, amask, use_dx10 = \
        _jc3_pixelformat(dxgi)

    out = bytearray()
    out += struct.pack("<I", 0x20534444)             # 'DDS '
    out += struct.pack("<I", 124)                    # Size
    out += struct.pack("<I", 0x1007 | 0x20000)       # Flags: Texture | Mipmap
    out += struct.pack("<I", height)
    out += struct.pack("<I", width)
    out += struct.pack("<I", 0)                       # PitchOrLinearSize
    out += struct.pack("<I", depth)
    out += struct.pack("<I", mipcount)               # MipMapCount
    out += b"\x00" * (11 * 4)                         # Reserved1[11]

    out += struct.pack("<I", 32)                      # PixelFormat.Size
    out += struct.pack("<I", flags)
    out += struct.pack("<I", fourcc)
    out += struct.pack("<I", rgb_bits)
    out += struct.pack("<I", rmask)
    out += struct.pack("<I", gmask)
    out += struct.pack("<I", bmask)
    out += struct.pack("<I", amask)

    out += struct.pack("<I", 0x8 | 0x1000)           # SurfaceFlags: COMPLEX | TEXTURE
    out += struct.pack("<I", 0)                       # CubemapFlags
    out += b"\x00" * (3 * 4)                          # Reserved2[3]

    if use_dx10:
        out += struct.pack("<I", dxgi)               # dxgiFormat
        out += struct.pack("<I", 3)                  # resourceDimension = 2D
        out += struct.pack("<I", 0)                  # miscFlag
        out += struct.pack("<I", 1)                  # arraySize
        out += struct.pack("<I", 0)                  # miscFlags2
    return bytes(out)


# ---- public: raw bytes ----------------------------------------------------
def ddsc_to_dds_bytes(ddsc_path):
    """Read a JC3 .ddsc (and its .hmddsc if present) and return complete DDS
    bytes plus a list of log lines. Raises ValueError on unsupported input."""
    log = []
    with open(ddsc_path, "rb") as f:
        ddsc_bytes = f.read()

    texture = _avtx_parse(ddsc_bytes)
    if texture is None:
        raise ValueError("Not a valid AVTX .ddsc: %s" % os.path.basename(ddsc_path))

    if (texture.flags & _AVTX_CUBEMAP_FLAG) or texture.depth > 1:
        raise ValueError("Texture is a cubemap/array; not converted.")

    hmddsc_path = os.path.splitext(ddsc_path)[0] + ".hmddsc"
    have_hmddsc = os.path.exists(hmddsc_path)
    hmddsc_bytes = None
    if have_hmddsc:
        with open(hmddsc_path, "rb") as f:
            hmddsc_bytes = f.read()

    # Non-empty elements, biggest mip first. Skip external (.hmddsc) mips when
    # the .hmddsc isn't on disk.
    ordered = []
    for i, el in enumerate(texture.elements):
        if el["size"] == 0:
            continue
        if el["is_external"] and not have_hmddsc:
            continue
        at = 0
        while at < len(ordered) and texture.elements[ordered[at]]["size"] >= el["size"]:
            at += 1
        ordered.insert(at, i)
    if not ordered:
        raise ValueError("No element data available to export.")

    # When the largest (external) mips are absent, the DDS describes only what
    # is present: rank = number of bigger mips we couldn't include.
    biggest = ordered[0]
    biggest_size = texture.elements[biggest]["size"]
    rank = 0
    for i, el in enumerate(texture.elements):
        if i != biggest and el["size"] > biggest_size:
            rank += 1

    eff_w = max(1, texture.width >> rank)
    eff_h = max(1, texture.height >> rank)
    eff_mips = max(1, texture.mip_count - rank)

    body = bytearray()
    for idx in ordered:
        el = texture.elements[idx]
        src = hmddsc_bytes if el["is_external"] else ddsc_bytes
        body += src[el["offset"]:el["offset"] + el["size"]]

    log.append("JC3: format=%d %dx%d mips=%d%s" % (
        texture.fmt, eff_w, eff_h, eff_mips,
        " (top %d mip(s) external, not on disk)" % rank if rank else ""))

    header = _write_jc3_dds_header(texture.fmt, eff_w, eff_h,
                                   texture.depth, eff_mips)
    return bytes(header + bytes(body)), log


# ---- caching + public entry points ----------------------------------------
def _ddsc_cache_path(ddsc_path, cache_root=None):
    if cache_root is None:
        cache_root = os.path.join(tempfile.gettempdir(), "io_import_rbm_ddsc_cache")
    abs_src = os.path.abspath(ddsc_path)
    dir_hash = hashlib.sha1(os.path.dirname(abs_src).encode("utf-8")).hexdigest()[:16]
    stem = os.path.splitext(os.path.basename(abs_src))[0]
    return os.path.join(cache_root, dir_hash, stem + ".dds")


def _ddsc_cache_is_fresh(ddsc_path, dds_path):
    if not os.path.exists(dds_path):
        return False
    dds_mtime = os.path.getmtime(dds_path)
    newest_src = os.path.getmtime(ddsc_path)
    hmddsc_path = os.path.splitext(ddsc_path)[0] + ".hmddsc"
    if os.path.exists(hmddsc_path):
        newest_src = max(newest_src, os.path.getmtime(hmddsc_path))
    return dds_mtime >= newest_src


def convert_ddsc_to_dds(ddsc_path, cache_root=None):
    """Convert a JC3 .ddsc to a cached .dds and return the .dds path, or None if
    the source is missing or can't be converted. The result is cached and reused
    on later imports (regenerated only when the source is newer)."""
    if not os.path.exists(ddsc_path):
        print(f"[ddsc->dds] source not found: {ddsc_path}")
        return None

    dds_path = _ddsc_cache_path(ddsc_path, cache_root)
    try:
        if _ddsc_cache_is_fresh(ddsc_path, dds_path):
            return dds_path

        dds_bytes, log = ddsc_to_dds_bytes(ddsc_path)
        os.makedirs(os.path.dirname(dds_path), exist_ok=True)
        tmp_path = dds_path + ".tmp"
        with open(tmp_path, "wb") as f:
            f.write(dds_bytes)
        os.replace(tmp_path, dds_path)

        for line in log:
            print(f"[ddsc->dds] {os.path.basename(ddsc_path)}: {line}")
        return dds_path
    except Exception as e:
        print(f"[ddsc->dds] conversion failed for {ddsc_path}: {e}")
        return None


def resolve_texture_filepath(on_disk_path):
    """Return a path Blender can load for the given on-disk texture path.

    Call sites build ``on_disk_path`` as usual (base path + the chosen texture
    extension). If that path is a raw JC3 .ddsc, it is converted to a .dds on the
    fly (pulling the high-res mip from the sibling .hmddsc) and the .dds path is
    returned. For every other extension the path is returned unchanged.
    """
    if not on_disk_path.lower().endswith(".ddsc"):
        return on_disk_path

    dds_path = convert_ddsc_to_dds(on_disk_path)
    if dds_path:
        return dds_path

    # Conversion unavailable: hand back the intended (non-existent) .dds path so
    # the caller's os.path.exists check reports "not found" cleanly, instead of
    # trying to load a raw .ddsc that Blender can't decode.
    return _ddsc_cache_path(on_disk_path)
