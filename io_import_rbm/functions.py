import os
import struct

# Helper functions for reading various binary data types
def read_u16(file):
    return int.from_bytes(file.read(2), 'little')

def read_s16(file):
    return int.from_bytes(file.read(2), 'little', signed=True)

def read_u32(file):
    return int.from_bytes(file.read(4), 'little')

def read_float(file):
    return struct.unpack('f', file.read(4))[0]

def read_string(file, length):
    return file.read(length).decode('utf-8')


# Function to convert a hex value to float using IEEE-754 format
def hex_to_float(hex_value):
    packed = struct.pack('>I', hex_value)
    return struct.unpack('>f', packed)[0]

# Function to decompress normal/tangent data
def decompress_normal(hex_value):
    f = hex_to_float(hex_value)
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
    r = read_s16(file) / 32767.0
    g = read_s16(file) / 32767.0
    b = read_s16(file) / 32767.0
    return r, g, b

# Function to process R16G16_UNORM format
def process_r16g16_unorm(file):
    r = read_u16(file) / 65535.0
    g = read_u16(file) / 65535.0
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