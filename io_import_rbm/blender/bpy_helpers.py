import bpy


def get_addon_preferences(name: str):
    addon = bpy.context.preferences.addons.get(name, None)
    if addon is None:
        return None

    return addon.preferences


def get_all_objects() -> set[bpy.types.Object]:
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
    for base_object in collection.objects:
        object_property = base_object.get(property_name)
        if object_property is None:
            continue

        if object_property == property_value:
            return base_object

    return None
