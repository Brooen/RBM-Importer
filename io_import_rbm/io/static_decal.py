import bpy
import math
import os
import mathutils
from py_atl.rtpc_v01.containers import RtpcStaticDecalObject

def load_static_decal(static_decal: RtpcStaticDecalObject):
    # Get preferences for the addon
    preferences = bpy.context.preferences.addons["io_import_rbm"].preferences
    extraction_base_path = preferences.extraction_base_path
    texture_extension = preferences.texture_extension


    def load_texture(texture_name):
        """Try loading the texture by replacing either '.ddsc' or '.tga'."""
        if texture_name.endswith(".ddsc") or texture_name.endswith(".tga"):
            texture_path = os.path.join(extraction_base_path, texture_name.rsplit(".", 1)[0] + texture_extension)
            if os.path.exists(texture_path):
                # Check if image is already loaded
                existing_image = bpy.data.images.get(os.path.basename(texture_path))
                if existing_image:
                    return existing_image
                return bpy.data.images.load(texture_path)
        return None

    # Create a plane
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    plane_object = bpy.context.object  # Get the newly created object

    # Rotate the plane 90 degrees on the X-axis
    plane_object.rotation_euler[0] = math.radians(-90)
    bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)

    # Create a new material
    material = bpy.data.materials.new(name=static_decal.name if static_decal.name else "StaticDecalMaterial")
    material.use_nodes = True
    plane_object.data.materials.append(material)

    # Get the material node tree
    nodes = material.node_tree.nodes
    links = material.node_tree.links
    nodes.clear()

    # Add the CStaticDecalObject node group
    if "CStaticDecalObject" in bpy.data.node_groups:
        decal_node = nodes.new(type='ShaderNodeGroup')
        decal_node.node_tree = bpy.data.node_groups["CStaticDecalObject"]
        decal_node.location = (0, 0)
    else:
        raise ValueError("Node group 'CStaticDecalObject' is missing in the scene.")

    # Add output node and link the result
    output_node = nodes.new(type='ShaderNodeOutputMaterial')
    output_node.location = (400, 0)
    links.new(decal_node.outputs["Result"], output_node.inputs["Surface"])

    # Add UV map node
    uv_node = nodes.new(type='ShaderNodeUVMap')
    uv_node.uv_map = "UVMap"  # Default UV map name
    uv_node.location = (-600, 200)

    def setup_texture(texture_name, mapping_params, color_input, alpha_input):
        """Sets up a texture with mapping and connections."""
        image = load_texture(texture_name)
        if image:
            # Set alpha mode for the image
            image.alpha_mode = 'CHANNEL_PACKED'

            # Add texture node
            texture_node = nodes.new(type='ShaderNodeTexImage')
            texture_node.image = image
            texture_node.location = (-400, 200 if color_input == "diffuse_texture" else -200)
            links.new(texture_node.outputs["Color"], decal_node.inputs[color_input])
            links.new(texture_node.outputs["Alpha"], decal_node.inputs[alpha_input])

            # Add mapping node
            mapping_node = nodes.new(type='ShaderNodeMapping')
            mapping_node.vector_type = 'POINT'
            mapping_node.location = (-500, 200 if color_input == "diffuse_texture" else -200)

            # Apply offset and tile values
            mapping_node.inputs['Location'].default_value[0] = mapping_params["offset_u"]
            mapping_node.inputs['Location'].default_value[1] = -mapping_params["offset_v"]  # Invert V offset
            mapping_node.inputs['Scale'].default_value[0] = mapping_params["tile_u"]
            mapping_node.inputs['Scale'].default_value[1] = mapping_params["tile_v"]

            # Link UV map to mapping
            links.new(uv_node.outputs["UV"], mapping_node.inputs["Vector"])
            # Link mapping to texture node
            links.new(mapping_node.outputs["Vector"], texture_node.inputs["Vector"])
        else:
            print(f"Texture '{texture_name}' not found.")

    # Set up diffuse texture
    if static_decal.diffuse_texture:
        setup_texture(static_decal.diffuse_texture, {
            "offset_u": static_decal.offset_u,
            "offset_v": static_decal.offset_v,
            "tile_u": static_decal.tile_u,
            "tile_v": static_decal.tile_v,
        }, "diffuse_texture", "diffuse_texture_alpha")

    # Set up alpha mask texture
    if static_decal.alphamask_texture:
        setup_texture(static_decal.alphamask_texture, {
            "offset_u": static_decal.alphamask_offset_u,
            "offset_v": static_decal.alphamask_offset_v,
            "tile_u": static_decal.alphamask_tile_u,
            "tile_v": static_decal.alphamask_tile_v,
        }, "alphamask_texture", "alphamask_texture_alpha")

    # Fill in shader parameters
    decal_node.inputs["is_distance_field_stencil"].default_value = static_decal.is_distance_field_stencil
    decal_node.inputs["alphamask_source_channel"].default_value = int(static_decal.alphamask_source_channel)
    decal_node.inputs["alpha_min"].default_value = static_decal.alpha_min
    decal_node.inputs["alpha_max"].default_value = static_decal.alpha_max
    decal_node.inputs["Emission"].default_value = static_decal.Emissive

    # Normalize color values by dividing by 255
    color_euler = static_decal.color
    decal_node.inputs["color"].default_value = (
        color_euler.x / 255.0,
        color_euler.y / 255.0,
        color_euler.z / 255.0,
        1.0  # Alpha is set to 1
    )

    return plane_object