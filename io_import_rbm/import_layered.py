import struct
import math
import bpy
import os
from functions import *

#This RenderBlock needs: Materials, UV extent/transforms, Scale, Flags

def process_block(filepath, file, imported_objects):
    print(f"Processing Layered block from {filepath}")

    # Set up the model name and clean it
    model_name = clean_filename(os.path.splitext(os.path.basename(filepath))[0])

    # Skip 73 bytes
    file.seek(file.tell() + 145)
    
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

    # Define filepath0 and hashed representation
    renderblocktype = "Layered" 
    if filepaths:
        # Clean filepath0 first
        cleaned_filepath0 = clean_material_name(os.path.basename(filepaths[0]))
        # Add hashed suffix
        hashed_suffix = hash_paths_and_type(filepaths, renderblocktype)
        filepath0 = f"{cleaned_filepath0} - id:{hashed_suffix}"
        print(f"Modified filepath0: {filepath0}")

    # Use filepath0 for the material name
    material_name = filepath0
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
    uv2_coords = []
    
    # Read vertex blocks with AmfFormat_R16G16B16_SNORM
    for i in range(vertcount):
        x, y, z = process_r16g16b16_snorm(file)
        unspecified = read_u16(file)
        vertices.append((x, y, z))
    
    # Vertex data section
    vertcount2 = read_u32(file)
    print(f"VertData Count: {vertcount2}")
    
    # Read vertdata blocks with AmfFormat_R16G16_UNORM for UVs
    for i in range(vertcount2):
        uv1 = process_r16g16_unorm(file)
        uv2 = process_r16g16_unorm(file)
        normal_hex = read_u32(file)
        tangent_hex = read_u32(file)
        color = read_float(file)
        
        # Decompress the normal and tangent
        normal_dec = decompress_normal(normal_hex)
        tangent_dec = decompress_normal(tangent_hex)
        
        uv1_coords.append(uv1)
        uv2_coords.append(uv2)
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
    uv_layer2 = mesh.uv_layers.new(name="UVMap_2")
    
    # Set UV coordinates
    for i, loop in enumerate(mesh.loops):
        uv_layer1.data[loop.index].uv = uv1_coords[loop.vertex_index]
        uv_layer2.data[loop.index].uv = uv2_coords[loop.vertex_index]
    
    # Add "Smooth by Angle" modifier
    modifier = mesh_obj.modifiers.new(name="Smooth by Angle", type='EDGE_SPLIT')
    modifier.split_angle = math.radians(30)  # Angle in radians
    modifier.use_edge_angle = True
    modifier.use_edge_sharp = False
    
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
