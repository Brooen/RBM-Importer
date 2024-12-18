import math
import bpy
from os import path
from io_import_rbm import functions
from io_import_rbm.io.stream import read_u16, read_u32, read_float, read_string


#This RenderBlock needs: Materials, UV extent/transforms, Scale, Flags

def process_block(filepath, file, imported_objects):
    print(f"Processing Landmark block from {filepath}")

    # Set up the model name and clean it
    model_name = functions.clean_filename(path.splitext(path.basename(filepath))[0])

    # Skip 89 bytes
    file.seek(file.tell() + 89)
    
    # Read u32 filepath slot count
    filepath_slot_count = read_u32(file)
    print(f"Filepath Slot Count: {filepath_slot_count}")
    
    # Read each filepath
    filepaths = []
    for i in range(filepath_slot_count):
        path_length = read_u32(file)
        file_path = read_string(file, path_length)
        filepaths.append(file_path)
        print(f"Filepath {i+1}: {file_path}")

    # Define filepath0 and hashed representation
    renderblocktype = "Landmark"  
    if filepaths:
        # Clean filepath0 first
        cleaned_filepath0 = functions.clean_material_name(path.basename(filepaths[0]))
        # Add hashed suffix
        hashed_suffix = functions.hash_paths_and_type(filepaths, renderblocktype)
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
    uv1_coords = []

    
    # Read vertex blocks with AmfFormat_R16G16B16_SNORM
    for i in range(vertcount):
        x, y, z = functions.process_r16g16b16_snorm(file)
        unspecified = read_u16(file)
        vertices.append((x, y, z))
    
    # Vertex data section
    vertcount2 = read_u32(file)
    print(f"VertData Count: {vertcount2}")
    
    # Read vertdata blocks with AmfFormat_R16G16_UNORM for UVs
    for i in range(vertcount2):
        uv1 = functions.process_r16g16_unorm(file)
        color = read_float(file)
        
        
        uv1_coords.append(uv1)

    
    
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
