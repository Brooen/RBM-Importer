import bpy
import os
import re
from mathutils import Matrix, Euler
import numpy as np
import math
import struct
from .functions import apply_transformations


def get_base_path():
    preferences = bpy.context.preferences.addons["io_import_rbm"].preferences
    return preferences.extraction_base_path


# Dictionary to track already imported meshes
imported_meshes = {}


def get_current_objects():
    return set(bpy.context.scene.objects)


def import_model(path, matrix_values, collection):
    global imported_meshes

    # Adjust the model file extension and prepend the base path
    base, _ = os.path.splitext(path)
    base_path = get_base_path()  # Dynamically fetch base path
    new_path = os.path.join(base_path, base + "_lod1.rbm")

    if not os.path.exists(new_path):
        print(f"Model file not found, skipping: {new_path}")
        return

    # Check if the model's mesh data is already imported
    if new_path in imported_meshes:
        # Create a new object that references the existing mesh
        mesh_data = imported_meshes[new_path]
        instance_obj = bpy.data.objects.new(mesh_data.name, mesh_data)
        # Apply transformations to the instance
        apply_transformations(instance_obj, matrix_values)
        instance_obj.scale = (1, 1, 1)

        collection.objects.link(instance_obj)
        return

    # Split new_path into directory and file name
    directory, filename = os.path.split(new_path)

    # Track objects before import
    before_import = get_current_objects()

    # Import the RBM model
    result = bpy.ops.import_scene.rbm_multi(
        directory=directory,
        files=[{"name": filename}],
        filter_glob="*.rbm"
    )

    # Check if the operation was successful
    if result != {'FINISHED'}:
        print(f"Failed to import {new_path}")
        return

    # Track objects after import
    after_import = get_current_objects()
    imported_objects = after_import - before_import

    for obj in imported_objects:
        # Only work with mesh objects
        if obj.type == 'MESH':
            # Store the mesh data in the dictionary
            imported_meshes[new_path] = obj.data
            apply_transformations(obj, matrix_values)
            obj.scale = (1, 1, 1)

            # Ensure the object is properly linked to the collection
            collection.objects.link(obj)
            bpy.context.scene.collection.objects.unlink(obj)
            break


def process_mdic(mdic_file_path):
    # Derive a collection name from the MDIC file name
    collection_name = os.path.splitext(os.path.basename(mdic_file_path))[0]
    collection = create_collection(collection_name)

    # Parse the MDIC file
    with open(mdic_file_path, 'rb') as f:
        header_data = f.read(4 * 8)
        header = struct.unpack('<' + 'I' * 8, header_data)
        if header[0] != 4801613: raise ValueError("File is not MDIC format")
        if header[1] != 12: raise ValueError("Unknown MDIC version")
        paths = []
        path_data = f.read(header[4])
        for i in range(header[2]):
            next_end = path_data.find(b'\0')
            path_ = path_data[:next_end]
            paths.append(path_.decode())
            path_data = path_data[next_end + 1:]
        tms = []
        for i in range(header[3]):
            tms.append(struct.unpack('<' + 'f' * 16, f.read(64)))
        for i in range(header[3]):
            index = struct.unpack('<H', f.read(2))[0]
            import_model(paths[index], tms[i], collection)


def create_collection(collection_name):
    if collection_name not in bpy.data.collections:
        new_collection = bpy.data.collections.new(collection_name)
        bpy.context.scene.collection.children.link(new_collection)
    return bpy.data.collections[collection_name]


def main(mdic_file_paths):
    for mdic_file_path in mdic_file_paths:
        process_mdic(mdic_file_path)


if __name__ == "__main__":
    print("This script is designed to be used as part of a Blender addon.")

print("Script completed.")
