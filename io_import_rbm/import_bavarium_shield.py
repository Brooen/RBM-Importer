import struct
import math
import bpy
import os


# Helper functions for reading various data types
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


def clean_filename(filename):
    # Remove `_lod#` from filename
    return filename.split('_lod')[0]



def process_block(filepath, file, imported_objects):
    print(f"Processing BavariumShield block from {filepath}")

    # Set up the model name and clean it
    model_name = clean_filename(os.path.splitext(os.path.basename(filepath))[0])

    # Skip 73 bytes
    file.seek(file.tell() + 1)
    


    # Read 70 floats for material data
    material_data = [read_float(file) for _ in range(4)]
    print("Material Data:", material_data)
        
    # Read u32 filepath slot count
    filepath_slot_count = read_u32(file)
    print(f"Filepath Slot Count: {filepath_slot_count}")
    
    # Read each filepath
    filepaths = []
    for i in range(filepath_slot_count):
        path_length = read_u32(file)
        path = read_string(file, path_length)
        filepaths.append(path)
        print(f"Filepath {i+1}: {path}")
    
    # Define the material name based on the available file paths
    material_name = "bavarium_shield"
    
    print(f"Material Name: {material_name}")
    
    # Skip 16 bytes
    file.seek(file.tell() + 16)
    
    # Read u32 vertcount
    vertcount = read_u32(file)
    print(f"Vertex Count: {vertcount}")
    
    vertices = []
    normals = []
    tangents = []
    uv1_coords = []

    
    # Loop over vertices
    for i in range(vertcount):
        x = read_float(file)
        y = read_float(file)
        z = read_float(file)
        vertices.append((x, y, z))
        uv1 = (read_float(file), read_float(file))
        
        normal_hex = read_u32(file)
        tangent_hex = read_u32(file)
        
        
        
        # Decompress the normal and tangent
        normal_dec = decompress_normal(normal_hex)
        tangent_dec = decompress_normal(tangent_hex)
        
        uv1_coords.append(uv1)
        
        normals.append(normal_dec)
        tangents.append(tangent_dec)
    
    
    # Read face count
    face_count = read_u32(file)
    print(f"Face Count: {face_count}")
    
    # Read indices and construct faces
    indices = [read_u16(file) for _ in range(face_count)]
    faces = [(indices[i], indices[i+1], indices[i+2]) for i in range(0, len(indices), 3)]
    
    # Read u32 endstring
    endstring = read_u32(file)
    print(f"End String: {endstring}")
    
    # Blender import - creating a single mesh for the file
    mesh = bpy.data.meshes.new(model_name)
    mesh_obj = bpy.data.objects.new(model_name, mesh)
    bpy.context.collection.objects.link(mesh_obj)
    
    # Create the mesh from vertices and faces
    mesh.from_pydata(vertices, [], faces)
    
    # Create UV maps
    uv_layer1 = mesh.uv_layers.new(name="UVMap_1")

    
    # Set UV coordinates
    for i, loop in enumerate(mesh.loops):
        uv_layer1.data[loop.index].uv = uv1_coords[loop.vertex_index]

    
    # Assign smooth shading
    for poly in mesh.polygons:
        poly.use_smooth = True
    
    # Create a material with the adjusted name and link it
    material = bpy.data.materials.get(material_name)
    if material is None:
        material = bpy.data.materials.new(name=material_name)
    mesh.materials.append(material)
    
    imported_objects.append(mesh_obj)
    

    print(f"Model '{model_name}' imported successfully with material '{material_name}'.")
