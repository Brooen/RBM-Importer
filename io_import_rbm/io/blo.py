
import bpy

from py_atl import development
from py_atl.rtpc_v01 import action, filters
from py_atl.rtpc_v01.containers import RtpcObject, RtpcWorldObject

from .rbm import load_rbm, create_collection

# these may produce expected warnings
from ApexFormat.RTPC.V01.Class import (RtpcV01HeaderExtensions, RtpcV01ContainerExtensions, RtpcV01Container,
                                       IRtpcV01Filter, RtpcV01Filter, RtpcV01FilterString)


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


def create_blender_objects(rtpc_rigidobject: RtpcWorldObject, parent_object: bpy.types.Object | None = None, import_damage_objects: bool = True) -> list:
    import functions
    blender_objects: list = []

    for rigid_object in rtpc_rigidobject.containers:
        model_object = load_rbm(rigid_object.filename, import_damage_objects=import_damage_objects)

        if model_object is None:
            continue

        model_object.parent = parent_object
        model_object.name = rigid_object.name if rigid_object.name is not None else rigid_object.name_hash
        functions.apply_transformations(model_object, rigid_object.world)

        blender_objects.append(model_object)
        blender_objects.extend(create_blender_objects(rigid_object, model_object, import_damage_objects))

    return blender_objects


def main(file_path: str, import_damage_objects: bool = True):
    import os

    container = load_blo_file(file_path)
    if container is None:
        return

    rtpc_rigidobject = filter_by_rigid_objects(container)
    blender_objects: list[bpy.types.Object] = create_blender_objects(rtpc_rigidobject, import_damage_objects=import_damage_objects)

    file_name_wo_ext: str = os.path.basename(file_path)
    file_collection: bpy.types.Collection = create_collection(file_name_wo_ext)

    for blender_object in blender_objects:
        file_collection.objects.link(blender_object)
        bpy.context.scene.collection.objects.unlink(blender_object)
