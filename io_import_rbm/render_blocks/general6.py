import math
import bpy
from os import path
from io_import_rbm import functions
from io_import_rbm.io.stream import read_u16, read_u32, read_float, read_string

#This RenderBlock needs:

# Flag definitions
BACKFACE_CULLING           = 0x1
TRANSPARENCY_ALPHABLENDING = 0x2
TRANSPARENCY_ALPHATESTING  = 0x4

def process_block(filepath, file, imported_objects):
    print(f"Processing General6 block from {filepath}")

    # Set up the model name and clean it
    model_name = functions.clean_filename(path.splitext(path.basename(filepath))[0])

    # Skip 73 bytes
    file.seek(file.tell() + 13)
    
    # Read scale factor and UV extents
    scale = read_float(file)
    UV1Extent = (read_float(file), read_float(file))
    UV2Extent = (read_float(file), read_float(file))
    file.seek(file.tell() + 8)  # Skip padding

    print(f"Scale Factor: {scale}")
    print(f"UV1Extent: {UV1Extent}")
    print(f"UV2Extent: {UV2Extent}")
    
    # Read flags
    flags = read_u32(file)
    print(f"Flags: {flags} ({bin(flags)})")
    
    # After reading the flags, skip 16 bytes
    file.seek(file.tell() + 24)
    
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
    renderblocktype = "General6"  
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
    
    # Read vertex blocks with AmfFormat_R16G16B16_SNORM
    for i in range(vertcount):
        x, y, z = functions.process_r16g16b16_snorm(file)
        x *= scale
        y *= scale
        z *= scale
        bone_index = read_u16(file)
        vertices.append((x, y, z))
    
    # Vertex data section
    vertcount2 = read_u32(file)
    print(f"VertData Count: {vertcount2}")
    
    # Read vertdata blocks with AmfFormat_R16G16_UNORM for UVs
    for i in range(vertcount2):
        uv1 = functions.process_r16g16_unorm(file)
        uv2 = functions.process_r16g16_unorm(file)
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

    # Transform UVs using extents
    uv1_coords = functions.transform_uvs(uv1_coords, UV1Extent)
    uv2_coords = functions.transform_uvs(uv2_coords, UV2Extent)
          
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

        material.use_nodes = True
        nodes = material.node_tree.nodes
        links = material.node_tree.links

        # Clear existing nodes
        for node in nodes:
            nodes.remove(node)

        # Create and configure the node group
        shader_node = nodes.new("ShaderNodeGroup")
        node_group = bpy.data.node_groups.get("General6")
        if not node_group:
            print("Node group 'General6' not found.")
        else:
            shader_node.node_tree = node_group
            shader_node.location = (0, 0)

        # Set boolean flags
        for i, flag in enumerate(bin(flags)[2:][::-1]):
            input_index = i
            if input_index < len(shader_node.inputs):
                if shader_node.inputs[input_index].type == "BOOLEAN":
                    shader_node.inputs[input_index].default_value = bool(int(flag))

        # Set textures
        
        # Fetch texture base path and extension from addon preferences
        addon_name = "io_import_rbm"  # Use the name from bl_info
        addon_prefs = bpy.context.preferences.addons[addon_name].preferences
        extraction_base_path = addon_prefs.extraction_base_path
        texture_extension = addon_prefs.texture_extension

        print(f"Texture Base Path: {extraction_base_path}")
        print(f"Texture Extension: {texture_extension}")

        # Define texture settings (matching Blender's 1-based indexing)
        TEXTURE_SETTINGS = {
            "uv1": [1, 2, 3,], #base
            "uv2": [4], #ao
            "srgb": [1],
            "non_color": [2, 3, 4],
        }

        input_index = 3  # Start at input index 3 to skip the first 3 inputs (this number is booleans)

        for texture_number, texture_path in enumerate(filepaths, start=1):  # Start at 1 for Blender indexing
            # Skip empty file paths
            if not texture_path.strip():
                print(f"Skipping empty texture path")
                input_index += 2  # Skip both color and alpha inputs
                continue

            # Construct the full file path
            texture_full_path = path.join(extraction_base_path, texture_path.replace(".ddsc", texture_extension))
            texture_name = path.basename(texture_full_path)  # Extract the file name

            print(f"Processing Texture {texture_number} at: {texture_full_path}")

            # Check if the image is already loaded
            existing_image = bpy.data.images.get(texture_name)
            if existing_image:
                print(f"Reusing existing image: {texture_name}")
                image = existing_image
            else:
                if path.exists(texture_full_path):
                    try:
                        # Load the image
                        image = bpy.data.images.load(texture_full_path)
                        image.alpha_mode = 'CHANNEL_PACKED'  # Set channel-packed alpha
                        print(f"Loaded new image: {texture_name}")
                    except Exception as e:
                        print(f"Error loading texture {texture_full_path}: {e}")
                        input_index += 2  # Skip both color and alpha inputs
                        continue
                else:
                    print(f"Texture file not found: {texture_full_path}")
                    input_index += 2  # Skip both color and alpha inputs
                    continue

            # Create texture node
            tex_node = nodes.new("ShaderNodeTexImage")
            tex_node.image = image
            tex_node.location = (-300, -100 * (input_index))

            # Set color space
            if texture_number in TEXTURE_SETTINGS.get("srgb", []):
                tex_node.image.colorspace_settings.name = "sRGB"
                print(f"Texture {texture_number}: Color space set to sRGB")
            elif texture_number in TEXTURE_SETTINGS.get("non_color", []):
                tex_node.image.colorspace_settings.name = "Non-Color"
                print(f"Texture {texture_number}: Color space set to Non-Color")

            # Create and assign UV Map node
            uv_node = nodes.new("ShaderNodeUVMap")
            if texture_number in TEXTURE_SETTINGS.get("uv1", []):
                uv_node.uv_map = "UVMap_1"
                print(f"Texture {texture_number}: Assigned to UV1")
            elif texture_number in TEXTURE_SETTINGS.get("uv2", []):
                uv_node.uv_map = "UVMap_2"
                print(f"Texture {texture_number}: Assigned to UV2")
            else:
                uv_node.uv_map = "UVMap_1"  # Default UV map
                print(f"Texture {texture_number}: Defaulted to UV1")

            uv_node.location = (-500, -100 * (input_index))

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
