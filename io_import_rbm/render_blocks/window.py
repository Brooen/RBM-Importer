import math
import os
import bpy
from os import path
from io_import_rbm import functions
from io_import_rbm.functions import load_ddsc_flags
from io_import_rbm.io.stream import read_u16, read_u32, read_float, read_string


#This RenderBlock needs: Flags

def process_block(filepath, file, imported_objects):
    print(f"Processing Window block from {filepath}")

    # Set up the model name and clean it
    model_name = functions.clean_filename(path.splitext(path.basename(filepath))[0])

    # Skip 1 byte
    file.seek(file.tell() + 1)

    # Read 6 floats for material data
    material_data = [read_float(file) for _ in range(6)]
    print("Material Data:", material_data)
    
    # Skip 16 bytes
    file.seek(file.tell() + 16)
    
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
    renderblocktype = "Window" 
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
    normals = []
    tangents = []
    uv1_coords = []
    uv2_coords = []
    
    # Loop over vertices
    for i in range(vertcount):
        x = read_float(file)
        y = read_float(file)
        z = read_float(file)
        vertices.append((x, y, z))
        uv1 = (read_float(file), read_float(file))
        uv2 = (read_float(file), read_float(file))
        normal_hex = read_u32(file)
        tangent_hex = read_u32(file)
        color = read_float(file)
        
        
        # Decompress the normal and tangent
        normal_dec = functions.decompress_normal(normal_hex)
        tangent_dec = functions.decompress_normal(tangent_hex)
        
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
    
    # Assign smooth shading
    for poly in mesh.polygons:
        poly.use_smooth = True
    
    # Create a material with the adjusted name and link it
    material = bpy.data.materials.get(material_name)
    if material is None:
        material = bpy.data.materials.new(name=material_name)
        mesh.materials.append(material)

        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        # Clear existing nodes
        for node in nodes:
            nodes.remove(node)

        # Create and configure the node group
        shader_node = nodes.new("ShaderNodeGroup")
        node_group = bpy.data.node_groups.get("Window")
        if not node_group:
            print("Node group 'Window' not found.")
        else:
            shader_node.node_tree = node_group
            shader_node.location = (0, 0)

        # Set textures
        
        
        # Set floats
        for i, float_value in enumerate(material_data[:6]):
            input_index = i + 0
            if input_index < len(shader_node.inputs):
                if shader_node.inputs[input_index].type == "VALUE":
                    shader_node.inputs[input_index].default_value = float_value
        
        # Fetch texture base path and extension from addon preferences
        addon_name = "io_import_rbm"  # Use the name from bl_info
        addon_prefs = bpy.context.preferences.addons[addon_name].preferences
        extraction_base_path = addon_prefs.extraction_base_path
        texture_extension = addon_prefs.texture_extension        # Automatically locate ddsc.db relative to this script
        current_dir = os.path.dirname(__file__)  # Directory of the current script
        parent_dir = os.path.abspath(os.path.join(current_dir, ".."))  # Parent directory
        ddsc_db_path = os.path.join(parent_dir, "ddsc.db")  # Path to ddsc.db
        ddsc_flags = load_ddsc_flags(ddsc_db_path)


        print(f"Texture Base Path: {extraction_base_path}")
        print(f"Texture Extension: {texture_extension}")

        # Define texture settings (matching Blender's 1-based indexing)
        TEXTURE_SETTINGS = {
            "uv1": [1, 2, 3, 4, 5, 6, 7],
            "uv2": [0],
        }

        input_index = 6  # Start at input index 83 to skip the first 80 inputs this number is booleans+floats

        for texture_number, texture_path in enumerate(filepaths, start=1):
            if not texture_path.strip():
                print(f"Skipping empty texture path")
                input_index += 2
                continue

            # Construct the full file path
            texture_full_path = path.join(extraction_base_path, texture_path.replace(".ddsc", texture_extension))
            texture_name = path.basename(texture_full_path)

            print(f"Processing Texture {texture_number} at: {texture_full_path}")

            # Load or reuse the image
            existing_image = bpy.data.images.get(texture_name)
            if existing_image:
                print(f"Reusing existing image: {texture_name}")
                image = existing_image
            else:
                if path.exists(texture_full_path):
                    try:
                        image = bpy.data.images.load(texture_full_path)
                        image.alpha_mode = 'CHANNEL_PACKED'
                        print(f"Loaded new image: {texture_name}")
                    except Exception as e:
                        print(f"Error loading texture {texture_full_path}: {e}")
                        input_index += 2
                        continue
                else:
                    print(f"Texture file not found: {texture_full_path}")
                    input_index += 2
                    continue

            # Debug: Print the texture path being looked up in the database
            print(f"Looking up texture path in ddsc.db: {texture_path}")

            # Determine color space based on flag
            flag = ddsc_flags.get(texture_path, 0)
            print(f"Flag value for {texture_path}: {flag:#06x}")  # Print flag as hex (e.g., 0x0008)

            if flag & 0x8:  # Check if the sRGB bit is set
                image.colorspace_settings.name = "sRGB"
                print(f"Texture {texture_number}: Color space set to sRGB")
            else:
                image.colorspace_settings.name = "Non-Color"
                print(f"Texture {texture_number}: Color space set to Non-Color")

            # Create texture node
            tex_node = nodes.new("ShaderNodeTexImage")  # Ensure tex_node is defined
            tex_node.image = image
            tex_node.location = (-300, -100 * (input_index))  # Adjust location for neat arrangement

            # Create and assign UV Map node
            uv_node = nodes.new("ShaderNodeUVMap")
            if texture_number in TEXTURE_SETTINGS.get("uv1", []):
                uv_node.uv_map = "UVMap_1"
                print(f"Texture {texture_number}: Assigned to UV1")
            elif texture_number in TEXTURE_SETTINGS.get("uv2", []):
                uv_node.uv_map = "UVMap_2"
                print(f"Texture {texture_number}: Assigned to UV2")
            elif texture_number in TEXTURE_SETTINGS.get("uv3", []):
                uv_node.uv_map = "UVMap_3"
                print(f"Texture {texture_number}: Assigned to UV3")
            else:
                uv_node.uv_map = "UVMap_1"  # Default UV map
                print(f"Texture {texture_number}: Defaulted to UV1")

            uv_node.location = (-500, -100 * (input_index))  # Subtract 83 for location offset

            # Connect UV map to texture
            links.new(uv_node.outputs["UV"], tex_node.inputs["Vector"])

            # Connect texture color to the current input index
            if input_index < len(shader_node.inputs):
                links.new(tex_node.outputs["Color"], shader_node.inputs[input_index])

            # Connect texture alpha to the next input index
            if input_index + 1 < len(shader_node.inputs):
                links.new(tex_node.outputs["Alpha"], shader_node.inputs[input_index + 1])

            # Increment the input index for the next texture (each texture uses 2 inputs)
            input_index += 2

    else:
        # Material already exists, reuse it
        print(f"Using existing material: {material_name}")

    # Assign the material to the mesh
    if material.name not in [mat.name for mat in mesh.materials]:
        mesh.materials.append(material)
    
    imported_objects.append(mesh_obj)

    print(f"Model '{model_name}' imported successfully with material '{material_name}'.")
