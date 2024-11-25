bl_info = {
    "name": "RBM Importer",
    "blender": (4, 2, 3),
    "category": "Import-Export",
    "description": "Imports RBM Files to blender",
    "author": "Brooen",
    "version": (1, 1, 0),
}


import importlib
import os
import sys
import bpy
from bpy.props import CollectionProperty, StringProperty
from bpy.types import Operator
from importlib import reload
from bpy.props import StringProperty
from bpy.types import AddonPreferences

# Set the importer path to the same directory as the addon
addon_path = os.path.dirname(__file__)
if addon_path not in sys.path:
    sys.path.append(addon_path)

# Dictionary to map render block types to their names and import functions
RENDER_BLOCK_TYPES = {
    0x2cec5ad5: ("GeneralMK3", "import_general_mk3"),
    0x483304d6: ("CarPaint14", "import_car_paint14"),
    0x5b2003f6: ("Window", "import_window"),
    0xdb948bf1: ("CarLight", "import_car_light"),
    0xa5d24ccd: ("BavariumShield", "import_bavarium_shield"),
    0xf99c72a1: ("WaterHull", "import_water_hull"),
    0xa7583b2b: ("General6", "import_general6"),
    0xb1f9133d: ("FoliageBark2", "import_foliage_bark2"),
    0x04894ecd: ("General3", "import_general3"),
    0xc7021ee3: ("Layered", "import_layered"),
    0x3b630e6d: ("Landmark", "import_landmark")
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
        relative_path = filepath.replace(base_path, "").lstrip("\\/")
        obj["filepath"] = relative_path
        print(f"Set relative filepath: {relative_path}")
    else:
        print(f"Base path not found in {filepath}. Filepath not set.")

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
                    print(f"Render Block {i+1}: Unknown Type (0x{renderblocktype:X}). Logging and Skipping.")
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

def register():
    bpy.utils.register_class(RBMImportOperator)
    bpy.utils.register_class(RBMImporterPreferences)  # Add preferences class
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(RBMImportOperator)
    bpy.utils.unregister_class(RBMImporterPreferences)  # Remove preferences class
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()
