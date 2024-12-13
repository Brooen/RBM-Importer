# RBM-Importer
A tool that imports Just Cause 3's RBM files into Blender
## Builds
[Latest Release](https://github.com/Brooen/RBM-Importer/releases/latest "Latest Release")

[Latest Test Build](https://github.com/Brooen/RBM-Importer/raw/refs/heads/main/io_import_rbm.zip "Latest Test Build")
## Supported RBMs
- GeneralMK3
- CarPaint14
- CarLight
- Window
- BavariumShield
- WaterHull
- General6
- FoliageBark2
- General3
- Layered - Needs materials, UVFix, and ScaleFix
- Landmark - Needs materials, UVFix, and ScaleFix
- VegetationFoliage
## MDIC Importing
Supports all MDIC files, MDIC files store static enviroment models.
## BLO Importing
Supports all BLO files, BLO files store props, lights(NOT YET IMPLEMENTED), and decals.

Requires the installation of [py_atl](https://github.com/EonZeNx/py-atl "py_atl")
## Contributors
- EonZeNx - creating py_atl, and making RTPC importing work properly
- PredatorCZ - ApexLib for referencing and also mapping out MDIC binaries
- SK83RJOSH - Helping with mesh normals
- Aaron Kirkham - JC Model Renderer source helped with figuring out shading data, mostly flags and texture slots
