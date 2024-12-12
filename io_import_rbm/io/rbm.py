"""

"""

from os import path
import bpy
from io_import_rbm.blender import bpy_helpers, bpy_addons


def import_rbm(file_path: str) -> bpy.types.Object | None:
    directory, filename = path.split(file_path)

    before_import = bpy_helpers.get_all_objects()
    result = bpy.ops.import_scene.rbm_multi(
        directory=directory,
        files=[{"name": filename}],
        filter_glob="*.rbm"
    )

    if result != {'FINISHED'}:
        print(f"Failed to import {file_path}")
        return

    after_import = bpy_helpers.get_all_objects()
    imported_objects = after_import - before_import

    if len(imported_objects) != 1:
        print(f"Failed to import {file_path}, too many imported objects")
        return

    return imported_objects.pop()


def is_debris(file_path: str) -> bool:
    DEBRIS_NAMES = ["debris", "dest", "dst", "dmg", "deformed", "chaos"]

    return any(debris_name in file_path.lower() for debris_name in DEBRIS_NAMES)


def load_rbm(file_path: str, relative: bool = True) -> bpy.types.Object | None:
    relative_target_path: str = file_path.replace(".lod", "_lod1.rbm")
    target_path: str = relative_target_path

    if relative:
        target_path = path.join(bpy_addons.get_base_path(), target_path)

    if not path.exists(target_path):
        print(f"Model file not found, skipping: {target_path}")
        return

    base_mesh_collection = bpy_helpers.get_base_mesh_collection()
    existing_object = bpy_helpers.get_object_from_collection(base_mesh_collection, "filepath", relative_target_path)

    if existing_object is None:
        existing_object = import_rbm(target_path)

        if existing_object is None:
            print(f"failed to load RBM file")
            return

        base_mesh_collection.objects.link(existing_object)
        bpy.context.scene.collection.objects.unlink(existing_object)

    linked_instance = existing_object.copy()
    linked_instance.data = existing_object.data

    bpy.context.scene.collection.objects.link(linked_instance)

    return linked_instance
