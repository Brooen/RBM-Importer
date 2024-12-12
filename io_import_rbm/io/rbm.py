"""

"""

from os import path
import bpy


def get_base_path() -> str:
    preferences = bpy.context.preferences.addons["io_import_rbm"].preferences
    return preferences.extraction_base_path


def get_current_objects() -> set:
    return set(bpy.context.scene.objects)


def create_collection(name: str) -> bpy.types.Collection:
    collection: bpy.types.Collection = bpy.data.collections.get(name)
    if collection is None:
        print(f"creating '{name}' collection")
        collection = bpy.data.collections.new(name)
        bpy.context.scene.collection.children.link(collection)

    return collection


def get_base_mesh_collection() -> bpy.types.Collection:
    COLLECTION_NAME: str = "Base mesh"

    collection: bpy.types.Collection = bpy.data.collections.get(COLLECTION_NAME)
    if collection is None:
        collection = create_collection(COLLECTION_NAME)

        view_layer = bpy.context.view_layer
        layer_collection = next((lc for lc in view_layer.layer_collection.children if lc.collection == collection), None)
        if layer_collection:
            print(f"excluding '{COLLECTION_NAME}' collection from view layer")
            layer_collection.exclude = True

    return collection


def get_object_from_collection(collection: bpy.types.Collection, property_name: str, property_value) -> bpy.types.Object | None:
    failed_matches: list[str] = []
    for base_object in collection.objects:
        object_property = base_object.get(property_name)
        if object_property is None:
            continue

        if object_property == property_value:
            return base_object

        failed_matches.append(object_property)

    return None


def import_rbm(target_path: str) -> bpy.types.Object | None:
    directory, filename = path.split(target_path)

    before_import = get_current_objects()
    result = bpy.ops.import_scene.rbm_multi(
        directory=directory,
        files=[{"name": filename}],
        filter_glob="*.rbm"
    )

    if result != {'FINISHED'}:
        print(f"Failed to import {target_path}")
        return

    after_import = get_current_objects()
    imported_objects = after_import - before_import

    if len(imported_objects) != 1:
        print(f"Failed to import {target_path}, too many imported objects")
        return

    return imported_objects.pop()


def load_rbm(file_path: str, relative: bool = True) -> bpy.types.Object | None:
    relative_target_path: str = file_path.replace(".lod", "_lod1.rbm")
    target_path: str = relative_target_path

    if relative:
        target_path = path.join(get_base_path(), target_path)

    if not path.exists(target_path):
        print(f"Model file not found, skipping: {target_path}")
        return

    base_mesh_collection = get_base_mesh_collection()
    existing_object = get_object_from_collection(base_mesh_collection, "filepath", relative_target_path)

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
