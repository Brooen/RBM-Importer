bl_info = {
    "name": "RBM Importer",
    "blender": (4, 2, 3),
    "category": "Import-Export",
    "description": "Imports RBM Files to blender",
    "author": "Brooen",
    "version": (1, 0, 0),
}


import importlib
import os
import sys
import bpy
from bpy.props import CollectionProperty, StringProperty
from bpy.types import Operator
from importlib import reload

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
    0xf99c72a1: ("WaterHull", "import_water_hull")
}

# Utility function to read 32-bit unsigned integers from binary files
def read_u32(file):
    return int.from_bytes(file.read(4), 'little')

# Main import function
def import_model(filepath):
    imported_objects = []
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
                    print(f"Render Block {i+1}: Unknown Type (0x{renderblocktype:X}). Skipping.")

            combine_imported_objects(imported_objects)

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

# Register and unregister functions
def register():
    bpy.utils.register_class(RBMImportOperator)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)

def unregister():
    bpy.utils.unregister_class(RBMImportOperator)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)

if __name__ == "__main__":
    register()