from io_import_rbm.blender import bpy_helpers


def get_base_path():
    preferences = bpy_helpers.get_addon_preferences("io_import_rbm")
    if preferences is None:
        return ""

    return preferences.extraction_base_path
