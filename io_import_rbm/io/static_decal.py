import bpy


def load_static_decal():
    # Creating a new plane
    bpy.ops.mesh.primitive_plane_add(size=1, location=(0, 0, 0))
    print("Plane created at (0, 0, 0).")
