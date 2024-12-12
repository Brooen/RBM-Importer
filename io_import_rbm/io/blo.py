
from os import path

from py_atl import development
from py_atl.rtpc_v01 import action, filters
from py_atl.rtpc_v01.containers import RtpcObject, RtpcWorldObject
import bpy

from io_import_rbm.io import rbm
from io_import_rbm.blender import bpy_helpers

# these may produce expected warnings
from ApexFormat.RTPC.V01.Class import (RtpcV01Container)


def load_blo_file(path: str) -> RtpcV01Container | None:
    container: RtpcV01Container | None = action.load_from_path(path)
    if container is None:
        development.log(f"failed to load container from '{path}'")
        return None

    return container


def filter_by_rigid_objects(container: RtpcV01Container) -> RtpcWorldObject:
    rtpc_rigidobject: RtpcObject = action.filter_by(container, [
        filters.RIGID_OBJECT,
    ])

    return rtpc_rigidobject


def create_rtpc_blender_objects(rtpc_rigidobject: RtpcWorldObject, parent_object: bpy.types.Object | None = None, load_damage_models: bool = True) -> list:
    import functions
    blender_objects: list = []

    for rigid_object in rtpc_rigidobject.containers:
        if not load_damage_models and rbm.is_debris(rigid_object.filename):
            continue

        model_object = rbm.load_rbm(rigid_object.filename)
        if model_object is None:
            continue

        model_object.parent = parent_object
        model_object.name = rigid_object.name if rigid_object.name is not None else rigid_object.name_hash
        functions.apply_transformations(model_object, rigid_object.world)

        blender_objects.append(model_object)
        blender_objects.extend(create_rtpc_blender_objects(rigid_object, model_object, load_damage_models))

    return blender_objects


def main(file_path: str, import_damage_objects: bool = True):
    if not path.exists(file_path):
        print(f"Model file not found, skipping: {file_path}")
        return

    container = load_blo_file(file_path)
    if container is None:
        return

    rtpc_rigidobject = filter_by_rigid_objects(container)
    blender_objects: list[bpy.types.Object] = create_rtpc_blender_objects(rtpc_rigidobject, load_damage_models=import_damage_objects)

    file_name: str = path.basename(file_path)
    file_name_wo_ext: str = path.splitext(file_name)[0]
    file_collection: bpy.types.Collection = bpy_helpers.create_collection(file_name_wo_ext)

    for blender_object in blender_objects:
        file_collection.objects.link(blender_object)
        bpy.context.scene.collection.objects.unlink(blender_object)
