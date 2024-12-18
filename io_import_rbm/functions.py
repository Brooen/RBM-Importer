import os
from mathutils import Matrix
import hashlib

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