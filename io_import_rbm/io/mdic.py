"""

"""

import struct
import mathutils
from os import path
from dataclasses import dataclass, field
import bpy

from io_import_rbm.io import rbm
from io_import_rbm.blender import bpy_helpers
from py_atl.dll import cs_to


@dataclass(slots=True)
class MdicFragment:
    file_path: str | None = field(init=False, default=None)
    world: mathutils.Matrix | None = field(init=False, default=None)


def load_mdic_file(file_path: str) -> list[MdicFragment]:
    fragments: list[MdicFragment] = []

    with open(file_path, 'rb') as f:
        header_data = f.read(4 * 8)
        header = struct.unpack('<' + 'I' * 8, header_data)

        if header[0] != 4801613:
            raise ValueError("File is not MDIC format")

        if header[1] != 12:
            raise ValueError("Unknown MDIC version")

        file_paths: list[str] = []
        file_paths_data = f.read(header[4])
        for i in range(header[2]):
            next_end = file_paths_data.find(b'\0')
            path_ = file_paths_data[:next_end]
            file_paths.append(path_.decode())
            file_paths_data = file_paths_data[next_end + 1:]

        transforms: list[list[float]] = []
        for i in range(header[3]):
            transforms.append(list(struct.unpack('<' + 'f' * 16, f.read(64))))

        for i in range(header[3]):
            index = struct.unpack('<H', f.read(2))[0]

            fragment: MdicFragment = MdicFragment()
            fragment.file_path = file_paths[index]
            fragment.world: mathutils.Matrix = cs_to.bpy_matrix(transforms[i])

            fragments.append(fragment)

    return fragments


def create_mdic_blender_objects(mdic_fragments: list[MdicFragment], load_damage_models: bool = True) -> list[bpy.types.Object]:
    import functions
    blender_objects: list[bpy.types.Object] = []

    for mdic_fragment in mdic_fragments:
        if not load_damage_models and rbm.is_debris(mdic_fragment.file_path):
            continue

        model_object = rbm.load_rbm(mdic_fragment.file_path)
        if model_object is None:
            continue

        model_object.name = path.splitext(path.basename(mdic_fragment.file_path))[0]
        functions.apply_transformations(model_object, mdic_fragment.world)

        blender_objects.append(model_object)

    return blender_objects


def main(file_path: str, import_damage_objects: bool = True):
    if not path.exists(file_path):
        print(f"Model file not found, skipping: {file_path}")
        return

    fragments: list[MdicFragment] = load_mdic_file(file_path)
    blender_objects: list[bpy.types.Object] = create_mdic_blender_objects(fragments, load_damage_models=import_damage_objects)

    file_name: str = path.basename(file_path)
    file_name_wo_ext: str = path.splitext(file_name)[0]
    file_collection: bpy.types.Collection = bpy_helpers.create_collection(file_name_wo_ext)

    for blender_object in blender_objects:
        file_collection.objects.link(blender_object)
        bpy.context.scene.collection.objects.unlink(blender_object)
