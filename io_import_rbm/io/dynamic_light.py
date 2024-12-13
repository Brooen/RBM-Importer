import bpy
import mathutils
import math
import hashlib
from py_atl.rtpc_v01.containers import RtpcDynamicLightObject

def load_dynamic_light(dynamic_light: RtpcDynamicLightObject):
    # Generate a unique hash based on light parameters
    hash_input = f"{dynamic_light.diffuse.x}{dynamic_light.diffuse.y}{dynamic_light.diffuse.z}" \
                 f"{dynamic_light.is_spot_light}{dynamic_light.multiplier}" \
                 f"{dynamic_light.on_during_daytime}{dynamic_light.projected_texture}" \
                 f"{dynamic_light.projected_texture_enabled}{dynamic_light.projected_texture_u_scale}" \
                 f"{dynamic_light.projected_texture_v_scale}{dynamic_light.radius}" \
                 f"{dynamic_light.spot_angle}{dynamic_light.spot_inner_angle}".encode()
    hash = hashlib.sha256(hash_input).hexdigest()[:8]  # Use the first 8 characters of the hash
    light_data_name = f"Dynamic Light - id:{hash}"

    # Check if light data with this name already exists
    if light_data_name in bpy.data.lights:
        light_data = bpy.data.lights[light_data_name]
        print(f"Reusing existing light data: {light_data_name}")
    else:
        # Determine light type
        light_type = 'SPOT' if dynamic_light.is_spot_light else 'POINT'
        light_data = bpy.data.lights.new(name=light_data_name, type=light_type)
        print(f"Created new light data: {light_data_name}")

        # Set light properties
        light_data.energy = dynamic_light.multiplier * 1000  # Adjust intensity with multiplier
        light_data.color = (
            dynamic_light.diffuse.x,
            dynamic_light.diffuse.y,
            dynamic_light.diffuse.z
        )
        light_data.shadow_soft_size = dynamic_light.radius / 3

        if light_type == 'SPOT':
            light_data.spot_size = math.radians(dynamic_light.spot_angle)
            light_data.spot_blend = dynamic_light.spot_inner_angle / dynamic_light.spot_angle

    # Create a new light object and link the light data
    light_object = bpy.data.objects.new(name="Dynamic Light Object", object_data=light_data)
    bpy.context.collection.objects.link(light_object)

    # Set additional properties as custom properties
    light_object["on_during_daytime"] = dynamic_light.on_during_daytime
    light_object["projected_texture"] = dynamic_light.projected_texture
    light_object["projected_texture_enabled"] = dynamic_light.projected_texture_enabled
    light_object["projected_texture_u_scale"] = dynamic_light.projected_texture_u_scale
    light_object["projected_texture_v_scale"] = dynamic_light.projected_texture_v_scale

    # Debug output for validation
    print(f"Dynamic Light object added: {light_object.name}")
    print(f"  Linked to data: {light_data.name}")
    print(f"  Energy: {light_data.energy}")
    print(f"  Color (Diffuse): {light_data.color}")

    return light_object