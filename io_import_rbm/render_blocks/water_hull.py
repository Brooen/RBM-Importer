import struct
import math
import bpy
import os
from functions import *

#This RenderBlock needs: 

def process_block(filepath, file, imported_objects):
    print(f"Processing WaterHull block from {filepath}")

    # Set up the model name and clean it
    model_name = clean_filename(os.path.splitext(os.path.basename(filepath))[0])

    # Skip 21 bytes
    file.seek(file.tell() + 21)
   
    # Define the material name based on the available file paths
    material_name = "waterhull"   
    print(f"Material Name: {material_name}")
       
    # Read u32 vertcount
    vertcount = read_u32(file)
    print(f"Vertex Count: {vertcount}")
    
    vertices = []
    
    # Loop over vertices
    for i in range(vertcount):
        x = read_float(file)
        y = read_float(file)
        z = read_float(file)
        vertices.append((x, y, z) 
    )
    
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
