"""
NETmix optical material configuration.

Supports surface-only and volumetric
representations of the TiO2 catalyst.
"""

from pathlib import Path


def configure_materials(
    project,
    p,
    metal_bodies,
    catalyst_bodies,
    glass_bodies,
    input_dir,
    catalytic_faces=None
):

    input_dir = Path(input_dir).resolve()

    mode = p.CATALYST_OPTICAL_MODE.lower()

    if mode not in ("surface", "volume"):
        raise ValueError(
            "CATALYST_OPTICAL_MODE must be "
            "'surface' or 'volume'."
        )

    # --------------------------------------------------------
    # CHECK REQUIRED INPUT FILES
    # --------------------------------------------------------

    required_files = [
        p.TIO2_SURFACE_FILE,
        p.GLASS_VOLUME_FILE
    ]

    if mode == "volume":

        if not p.TIO2_VOLUME_FILE:
            raise ValueError(
                "A TiO2 volume material file is required "
                "for the volumetric optical model."
            )

        required_files.append(
            p.TIO2_VOLUME_FILE
        )

    for filename in required_files:

        path = input_dir / filename

        if not path.is_file():
            raise FileNotFoundError(path)

    if not metal_bodies or not glass_bodies:
        raise ValueError(
            "Metal and glass geometries are required."
        )

    if mode == "surface" and not catalytic_faces:
        raise ValueError(
            "Catalytic interface faces must be supplied."
        )

    if mode == "volume" and not catalyst_bodies:
        raise ValueError(
            "Catalyst bodies must be supplied."
        )

    materials = {}

    # --------------------------------------------------------
    # METAL PLATE
    # --------------------------------------------------------

    metal = project.create_optical_property(
        name="Metal_Plate"
    )

    metal.set_volume_opaque()

    metal.set_surface_mirror()

    metal.sop_mirror.reflectance = (
        p.METAL_REFLECTANCE
    )

    metal.geometries = metal_bodies

    metal.commit()

    materials["metal"] = metal

    print("Metal optical properties configured.")

    # --------------------------------------------------------
    # BOROSILICATE GLASS
    # --------------------------------------------------------

    glass = project.create_optical_property(
        name="Borosilicate_Glass"
    )

    glass.set_volume_library()

    glass.vop_library.material_file_uri = str(
        input_dir / p.GLASS_VOLUME_FILE
    )

    glass.set_surface_opticalpolished()

    glass.geometries = glass_bodies

    glass.commit()

    materials["glass"] = glass

    print("Glass optical properties configured.")

    # --------------------------------------------------------
    # TiO2 CATALYST
    # --------------------------------------------------------

    catalyst = project.create_optical_property(
        name="TiO2_Catalyst"
    )

    scattering_file = (
        input_dir / p.TIO2_SURFACE_FILE
    ).resolve()

    if not scattering_file.is_file():

        raise FileNotFoundError(scattering_file)

    # Surface optical properties

    catalyst.set_surface_library()

    catalyst.sop_library.file_uri = str(
        scattering_file
    )

    # Verify the assigned file path

    print(
        "TiO2 scattering file:",
        catalyst.sop_library.file_uri
    )

    # --------------------------------------------------------
    # CATALYST REPRESENTATION
    # --------------------------------------------------------

    if mode == "surface":

        catalyst.geometries = catalytic_faces

        print("Catalyst model: surface only.")

    elif mode == "volume":

        catalyst.set_volume_library()

        catalyst.vop_library.material_file_uri = str(
            input_dir / p.TIO2_VOLUME_FILE
        )

        catalyst.geometries = catalyst_bodies

        print("Catalyst model: volumetric.")

    # --------------------------------------------------------
    # COMMIT OPTICAL PROPERTY
    # --------------------------------------------------------

    catalyst.commit()

    materials["catalyst"] = catalyst

    print("TiO2 optical properties configured.")
    print("All optical materials configured.")

    return materials