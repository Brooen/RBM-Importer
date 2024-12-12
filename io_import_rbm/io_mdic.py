import bpy
import os
import re
from mathutils import Matrix, Euler
import numpy as np
import math
import struct
from .functions import apply_transformations
from .io.rbm import load_rbm, get_base_mesh_collection


def get_base_path():
    preferences = bpy.context.preferences.addons["io_import_rbm"].preferences
    return preferences.extraction_base_path




def get_current_objects():
    return set(bpy.context.scene.objects)


def import_model(path, matrix_values, collection):
    # Adjust the model file extension and prepend the base path
    base, _ = os.path.splitext(path)
    base_path = get_base_path()  # Dynamically fetch base path
    new_path = os.path.join(base_path, base + "_lod1.rbm")

    if not os.path.exists(new_path):
        print(f"Model file not found, skipping: {new_path}")
        return

    # Get the "Base mesh" collection
    base_mesh_collection = get_base_mesh_collection()

    # Check if the base mesh is already imported
    base_object = next(
        (obj for obj in base_mesh_collection.objects if obj.get("filepath") == new_path), None
    )

    if base_object is None:
        # Attempt to load the base mesh
        base_object = load_rbm(new_path)
        if base_object is None:
            print(f"Failed to import base mesh: {new_path}")
            return

        # Add metadata to identify the file path
        base_object["filepath"] = new_path

        # Ensure it's only linked to the base mesh collection
        base_mesh_collection.objects.link(base_object)

    # Check for an existing instance in the target collection
    instance_object = next(
        (obj for obj in collection.objects if obj.data == base_object.data), None
    )

    if instance_object is None:
        # Create a linked duplicate for the instance
        instance_object = base_object.copy()
        instance_object.data = base_object.data  # Share mesh data

        # Apply transformations
        apply_transformations(instance_object, matrix_values)
        instance_object.scale = (1, 1, 1)

        # Link the instance to the target collection
        collection.objects.link(instance_object)


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
