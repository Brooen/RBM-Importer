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

def clean_material_name(filepath):
    # Remove `_dif` from the end and strip file extension
    base_name = os.path.splitext(filepath)[0]  # Remove extension
    return base_name.replace('_dif', '')

def process_block(filepath, file, imported_objects):
    print(f"Processing Window block from {filepath}")

    # Set up the model name and clean it
    model_name = clean_filename(os.path.splitext(os.path.basename(filepath))[0])

    # Skip 73 bytes
    file.seek(file.tell() + 1)

    # Read 70 floats for material data
    material_data = [read_float(file) for _ in range(6)]
    print("Material Data:", material_data)
    
    file.seek(file.tell() + 16)
    
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
    material_name = clean_material_name(os.path.basename(filepaths[0]))
    material_name += f" - window"
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
    texture_extension = addon_prefs.texture_extension

    print(f"Texture Base Path: {extraction_base_path}")
    print(f"Texture Extension: {texture_extension}")

    # Define texture settings (matching Blender's 1-based indexing)
    TEXTURE_SETTINGS = {
        "uv1": [1, 2, 3, 4, 5, 6, 7],
        "uv2": [0],
        #"uv3": [0],  # Optional if needed
        "srgb": [1],
        "non_color": [2, 3, 4, 5, 6, 7],
    }

    input_index = 6  # Start at input index 83 to skip the first 80 inputs this number is booleans+floats

    for texture_number, texture_path in enumerate(filepaths, start=1):  # Start at 1 for Blender indexing
        # Skip empty file paths
        if not texture_path.strip():
            print(f"Skipping empty texture path")
            input_index += 2  # Skip both color and alpha inputs
            continue

        # Construct the full file path
        texture_full_path = os.path.join(extraction_base_path, texture_path.replace(".ddsc", texture_extension))
        texture_name = os.path.basename(texture_full_path)  # Extract the file name

        print(f"Processing Texture {texture_number} at: {texture_full_path}")

        # Check if the image is already loaded
        existing_image = bpy.data.images.get(texture_name)
        if existing_image:
            print(f"Reusing existing image: {texture_name}")
            image = existing_image
        else:
            if os.path.exists(texture_full_path):
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
        tex_node.location = (-300, -100 * (input_index))  # Subtract 83 for location offset

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


    
    imported_objects.append(mesh_obj)

    print(f"Model '{model_name}' imported successfully with material '{material_name}'.")
