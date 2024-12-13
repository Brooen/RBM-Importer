
from os import path

from py_atl import development
from py_atl.rtpc_v01 import action, filters
from py_atl.rtpc_v01.containers import RtpcObject, RtpcWorldObject, RtpcRigidObject, RtpcStaticDecalObject, RtpcDynamicLightObject
import bpy

from io_import_rbm.io import rbm, static_decal, dynamic_light
from io_import_rbm.blender import bpy_helpers

# these may produce expected warnings
from ApexFormat.RTPC.V01.Class import (RtpcV01Container)


def load_blo_file(file_path: str) -> RtpcV01Container | None:
    container: RtpcV01Container | None = action.load_from_path(file_path)
    if container is None:
        development.log(f"failed to load container from '{file_path}'")
        return None

    return container


def filter_by_supported(container: RtpcV01Container) -> RtpcObject:
    rtpc_world_objects: RtpcObject = action.filter_by(container, [
        filters.RIGID_OBJECT,
        filters.STATIC_DECAL_OBJECT,
        filters.DYNAMIC_LIGHT_OBJECT
    ])

    return rtpc_world_objects


def create_rtpc_blender_objects(rtpc_world_object: RtpcWorldObject, parent_object: bpy.types.Object | None = None,
                                load_damage_models: bool = True) -> list:
    import functions
    blender_objects: list = []

    for world_object in rtpc_world_object.containers:
        if hasattr(world_object, "filename"):
            if not load_damage_models and rbm.is_debris(world_object.filename):
                continue

        model_object: bpy.types.Object | None = None
        if isinstance(world_object, RtpcRigidObject):
            model_object = rbm.load_rbm(world_object.filename)
        elif isinstance(world_object, RtpcStaticDecalObject):
            model_object = static_decal.load_static_decal(world_object)
        elif isinstance(world_object, RtpcDynamicLightObject):
            model_object = dynamic_light.load_dynamic_light(world_object)

        else:
            development.log(f"unsupported rtpc_world_object: {type(rtpc_world_object)}")
            continue

        if model_object is None:
            continue

        model_object.parent = parent_object
        model_object.name = world_object.name if world_object.name is not None else world_object.name_hash
        functions.apply_transformations(model_object, world_object.world)

        blender_objects.append(model_object)
        blender_objects.extend(create_rtpc_blender_objects(world_object, model_object, load_damage_models))

    return blender_objects


def main(file_path: str, import_damage_objects: bool = True):
    if not path.exists(file_path):
        print(f"Model file not found, skipping: {file_path}")
        return

    container = load_blo_file(file_path)
    if container is None:
        return

    rtpc_world_objects: RtpcObject = filter_by_supported(container)
    blender_objects: list[bpy.types.Object] = create_rtpc_blender_objects(rtpc_world_objects, load_damage_models=import_damage_objects)

    file_name: str = path.basename(file_path)
    file_name_wo_ext: str = path.splitext(file_name)[0]
    file_collection: bpy.types.Collection = bpy_helpers.create_collection(file_name_wo_ext)

    for blender_object in blender_objects:
        file_collection.objects.link(blender_object)
        bpy.context.scene.collection.objects.unlink(blender_object)
