bl_info = {
    "name": "RBM Importer",
    "blender": (4, 2, 3),
    "category": "Import-Export",
    "description": "Imports RBM Files to blender",
    "author": "Brooen",
    "version": (1, 4, 0),
}

import importlib
import os
import sys
import bpy
from bpy.props import CollectionProperty
from bpy.types import Operator
from importlib import reload
from bpy.props import StringProperty
from bpy.types import AddonPreferences
from io_import_rbm.io import mdic

# Set the importer path to the same directory as the addon
addon_path = os.path.dirname(__file__)
if addon_path not in sys.path:
    sys.path.append(addon_path)

# Dictionary to map render block types to their names and import functions
RENDER_BLOCK_TYPES = {
    0x2cec5ad5: ("GeneralMK3",          "io_import_rbm.render_blocks.general_mk3"),
    0x2ee0f4a9: ("GeneralSimple",       "io_import_rbm.render_blocks.general_simple"),
    0x3b630e6d: ("Landmark",            "io_import_rbm.render_blocks.landmark"),
    0x5b2003f6: ("Window",              "io_import_rbm.render_blocks.window"),
    0x9d6e332a: ("CharacterClothes9",   "io_import_rbm.render_blocks.character_clothes9"),
    0x35bf53d5: ("GeneralSimple3",      "io_import_rbm.render_blocks.general_simple3"),
    0x626f5e3b: ("CharacterSkin6",      "io_import_rbm.render_blocks.character_skin6"),
    0x04894ecd: ("General3",            "io_import_rbm.render_blocks.general3"),
    0x483304d6: ("CarPaint14",          "io_import_rbm.render_blocks.car_paint14"),
    0xa5d24ccd: ("BavariumShield",      "io_import_rbm.render_blocks.bavarium_shield"),
    0xa7583b2b: ("General6",            "io_import_rbm.render_blocks.general6"),
    0xb1f9133d: ("FoliageBark2",        "io_import_rbm.render_blocks.foliage_bark2"),
    0xc7021ee3: ("Layered",             "io_import_rbm.render_blocks.layered"),
    0xd79884c6: ("VegetationFoliage",   "io_import_rbm.render_blocks.vegetation_foliage"),
    0xdb948bf1: ("CarLight",            "io_import_rbm.render_blocks.car_light"),
    0xf99c72a1: ("WaterHull",           "io_import_rbm.render_blocks.water_hull"),
}


def ensure_shaders_nodegroup():
    """Ensure the '.Shaders' node group is present, appending it if necessary."""
    shaders_node_name = ".Shaders"
    if shaders_node_name not in bpy.data.node_groups:
        # Path to shaders.blend in the addon directory
        shaders_blend_path = os.path.join(addon_path, "shaders.blend")
        try:
            with bpy.data.libraries.load(shaders_blend_path, link=False) as (data_from, data_to):
                if shaders_node_name in data_from.node_groups:
                    data_to.node_groups.append(shaders_node_name)
                    print(f"'{shaders_node_name}' node group appended from {shaders_blend_path}")
                else:
                    print(f"Node group '{shaders_node_name}' not found in {shaders_blend_path}")
        except Exception as e:
            print(f"Error appending '{shaders_node_name}': {e}")
    else:
        print(f"'{shaders_node_name}' node group already exists.")


# Utility function to read 32-bit unsigned integers from binary files
def read_u32(file):
    return int.from_bytes(file.read(4), 'little')


# Function to compute the relative filepath and set it as a custom property
def set_relative_filepath(obj, filepath, base_path):
    if base_path in filepath:
        relative_path = filepath.replace(base_path, "").lstrip("\\/").replace("\\", "/")
        obj["filepath"] = relative_path
        print(f"Set relative filepath: {relative_path}")
    else:
        print(f"Base path {base_path} not found in {filepath}. Filepath not set.")


# Main import function
def import_model(filepath):
    preferences = bpy.context.preferences.addons[__name__].preferences
    extraction_base_path = preferences.extraction_base_path
    ensure_shaders_nodegroup()  # Ensure the .Shaders node group is present
    imported_objects = []
    unrecognized_blocks_path = os.path.join(addon_path, "unrecognized_blocks.txt")  # Path for log file

    try:
        with open(filepath, 'rb') as file:
            file.seek(45)
            renderblockcount = read_u32(file)
            print(f"Render Block Count: {renderblockcount}")
            file.seek(file.tell() + 4)

            for i in range(renderblockcount):
                renderblocktype = read_u32(file)
                block_name, import_module_name = RENDER_BLOCK_TYPES.get(renderblocktype, (None, None))

                if block_name:
                    import_block(filepath, file, import_module_name, imported_objects)
                else:
                    print(f"Render Block {i + 1}: Unknown Type (0x{renderblocktype:X}). Logging and Skipping.")
                    # Log the filepath to the text file
                    with open(unrecognized_blocks_path, 'a') as log_file:
                        log_file.write(f"{filepath}\n")

            combine_imported_objects(imported_objects)

            # Set the relative file path for imported objects
            for obj in imported_objects:
                set_relative_filepath(obj, filepath, extraction_base_path)

    except Exception as e:
        print(f"Error importing model: {e}")


# Function to import a render block by dynamically loading the module
def import_block(filepath, file, module_name, imported_objects):
    try:
        block_module = importlib.import_module(module_name)
        reload(block_module)
        block_module.process_block(filepath, file, imported_objects)
    except ModuleNotFoundError:
        print(f"Module '{module_name}' not found for render block import.")


# Function to combine all imported objects into a single mesh
def combine_imported_objects(objects):
    if not objects:
        print("No objects to combine.")
        return

    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)

    bpy.ops.object.join()
    print(f"Combined {len(objects)} objects into a single mesh.")

    # Rotate the combined object by -90 degrees on the X-axis
    bpy.context.object.rotation_euler[0] = 1.5708  # 90 degrees in radians


# Operator to handle the import functionality
class RBMImportOperator(Operator):
    bl_idname = "import_scene.rbm_multi"
    bl_label = "Import Multiple RBM Models"
    bl_description = "Import multiple RBM model files"
    bl_options = {'REGISTER', 'UNDO'}

    files: CollectionProperty(type=bpy.types.PropertyGroup)
    directory: StringProperty(subtype='DIR_PATH')
    filter_glob: StringProperty(default="*.rbm", options={'HIDDEN'})

    def execute(self, context):
        for file in self.files:
            filepath = os.path.join(self.directory, file.name)
            import_model(filepath)
        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}


class MDICImportOperator(Operator):
    """Import MDIC Files"""
    bl_idname = "import_scene.mdic"
    bl_label = "Import MDIC Files"
    bl_description = "Import MDIC files with associated models"
    bl_options = {'REGISTER', 'UNDO'}

    files: CollectionProperty(type=bpy.types.PropertyGroup)
    directory: StringProperty(subtype='DIR_PATH')
    filter_glob: StringProperty(default="*.mdic", options={'HIDDEN'})
    recursive: bpy.props.BoolProperty(
        name="Recursive",
        description="Import MDIC files recursively from subdirectories",
        default=False
    )

    def execute(self, context):
        preferences = bpy.context.preferences.addons[__name__].preferences
        base_path = preferences.extraction_base_path  # Shared base path

        # Collect file paths
        if self.recursive:
            mdic_file_paths = []
            for root, _, files in os.walk(self.directory):
                for file in files:
                    if file.endswith(".mdic"):
                        mdic_file_paths.append(os.path.join(root, file))
        else:
            mdic_file_paths = [os.path.join(self.directory, file.name) for file in self.files]

        # Process each MDIC file
        for mdic_file_path in mdic_file_paths:
            mdic.load_mdic(mdic_file_path)

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "recursive")


def menu_func_import_mdic(self, context):
    self.layout.operator(MDICImportOperator.bl_idname, text="MDIC Files (.mdic)")


class BLOImportOperator(Operator):
    """Import BLO Files"""
    bl_idname = "import_scene.blo"
    bl_label = "Import BLO Files"
    bl_description = "Import BLO files with associated models"
    bl_options = {'REGISTER', 'UNDO'}

    files: CollectionProperty(type=bpy.types.PropertyGroup)
    directory: StringProperty(subtype='DIR_PATH')
    filter_glob: StringProperty(default="*.blo", options={'HIDDEN'})
    recursive: bpy.props.BoolProperty(
        name="Recursive",
        description="Import BLO files recursively from subdirectories",
        default=False
    )

    import_damage_objects: bpy.props.BoolProperty(
        name="Import Damage Objects",
        description="Include objects with 'debris', 'dest', 'dst', or 'dmg' in their filenames",
        default=False
    )

    def execute(self, context):
        from io_import_rbm.io import blo  # Correct import for blo.py

        # Collect file paths
        if self.recursive:
            blo_file_paths = []
            for root, _, files in os.walk(self.directory):
                for file in files:
                    if file.endswith(".blo"):
                        blo_file_paths.append(os.path.join(root, file))
        else:
            blo_file_paths = [os.path.join(self.directory, file.name) for file in self.files]

        # Process each BLO file
        for blo_file_path in blo_file_paths:
            print(f"Processing BLO file: {blo_file_path}")
            try:
                blo.main(blo_file_path, import_damage_objects=self.import_damage_objects)  # Pass the toggle
            except Exception as e:
                self.report({'ERROR'}, f"Failed to process {blo_file_path}: {e}")
                print(f"Error processing BLO file: {blo_file_path}, {e}")

        return {'FINISHED'}

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "recursive")
        layout.prop(self, "import_damage_objects")  # Add the boolean property to the UI


def menu_func_import_blo(self, context):
    self.layout.operator(BLOImportOperator.bl_idname, text="BLO Files (.blo)")


# Register function to add the operator to the import menu
def menu_func_import(self, context):
    self.layout.operator(RBMImportOperator.bl_idname, text="RBM Model (.rbm)")


class RBMImporterPreferences(AddonPreferences):
    bl_idname = __name__

    extraction_base_path: StringProperty(
        name="Extraction Base Path",
        description="Base path for extracted files (models and textures)",
        default="",
        subtype='DIR_PATH'
    )

    texture_extension: StringProperty(
        name="Texture Extension",
        description="File extension for texture files",
        default=".png"
    )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "extraction_base_path")
        layout.prop(self, "texture_extension")

        if "py_atl" not in bpy.context.preferences.addons:
            layout.label(
                text="Warning: PyAtl is not installed or enabled! Expect errors",
                icon="ERROR"
            )
        else:
            layout.label(text="PyAtl is installed and enabled.", icon="CHECKMARK")


def register():
    bpy.utils.register_class(RBMImportOperator)
    bpy.utils.register_class(RBMImporterPreferences)  # Add preferences class

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.utils.register_class(MDICImportOperator)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_mdic)

    bpy.utils.register_class(BLOImportOperator)  # Register BLO operator
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_blo)  # Add BLO to menu


def unregister():
    bpy.utils.unregister_class(RBMImportOperator)
    bpy.utils.unregister_class(RBMImporterPreferences)  # Remove preferences class

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.utils.register_class(MDICImportOperator)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_mdic)

    bpy.utils.unregister_class(BLOImportOperator)  # Unregister BLO operator
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_blo)  # Remove BLO from menu


if __name__ == "__main__":
    register()
