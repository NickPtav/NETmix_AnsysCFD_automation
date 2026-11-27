"""
NETmix LED surface source configuration.

Creates independent LED sources using the original
angular and spectral distribution library files.
"""

from pathlib import Path

from ansys.speos.core.source import SourceSurface


def configure_sources(
    project,
    p,
    led_faces,
    input_dir
):

    input_dir = Path(input_dir).resolve()

    intensity_file = (
        input_dir / p.LED_INTENSITY_FILE
    ).resolve()

    spectrum_file = (
        input_dir / p.LED_SPECTRUM_FILE
    ).resolve()

    # --------------------------------------------------------
    # VALIDATE INPUT FILES
    # --------------------------------------------------------

    for path in [intensity_file, spectrum_file]:

        if not path.is_file():

            raise FileNotFoundError(path)

    if intensity_file.suffix.lower() != ".ies":

        raise ValueError(
            f"Expected an IES file: {intensity_file}"
        )

    if spectrum_file.suffix.lower() != ".spectrum":

        raise ValueError(
            f"Expected a spectrum file: {spectrum_file}"
        )

    print(f"LED intensity file: {intensity_file}")
    print(f"LED spectrum file: {spectrum_file}")

    # --------------------------------------------------------
    # VALIDATE LED COUNT
    # --------------------------------------------------------

    expected_leds = p.LED_ROWS * p.LED_COLUMNS

    if len(led_faces) != expected_leds:

        raise ValueError(
            f"Expected {expected_leds} LED faces, "
            f"received {len(led_faces)}."
        )

    sources = []

    # --------------------------------------------------------
    # CREATE LED SOURCES
    # --------------------------------------------------------

    for i, led in enumerate(led_faces, start=1):

        name = f"LED_{i:03d}"

        face = led["face"]

        reverse_normal = led["reverse_normal"]

        axis_system = led["axis_system"]

        source = project.create_source(
            name=name,
            feature_type=SourceSurface
        )

        # ----------------------------------------------------
        # EMITTING SURFACE
        # ----------------------------------------------------

        source.set_exitance_constant().geometries = [
            (face, reverse_normal)
        ]

        # ----------------------------------------------------
        # RADIANT POWER
        # ----------------------------------------------------

        source.flux.set_radiant()

        source.flux.value = p.LED_RADIANT_POWER_W

        # ----------------------------------------------------
        # ANGULAR INTENSITY DISTRIBUTION
        # ----------------------------------------------------

        intensity = source.intensity.set_library()

        intensity.intensity_file_uri = str(
            intensity_file
        )

        intensity.orientation_axis_system = axis_system

        # ----------------------------------------------------
        # SPECTRAL DISTRIBUTION
        # ----------------------------------------------------

        spectrum = source.spectrum.set_library()

        spectrum.file_uri = str(
            spectrum_file
        )

        # ----------------------------------------------------
        # VERIFY CONFIGURATION BEFORE COMMIT
        # ----------------------------------------------------

        if not intensity.intensity_file_uri:

            raise RuntimeError(
                f"{name}: intensity file URI is empty."
            )

        if not spectrum.file_uri:

            raise RuntimeError(
                f"{name}: spectrum file URI is empty."
            )

        if i == 1:

            print("\nFirst LED configuration:")

            print(
                "  Intensity:",
                intensity.intensity_file_uri
            )

            print(
                "  Spectrum:",
                spectrum.file_uri
            )

            print(
                "  Orientation:",
                intensity.orientation_axis_system
            )

            print(
                "  Radiant power:",
                source.flux.value,
                "W"
            )

        # ----------------------------------------------------
        # COMMIT SOURCE
        # ----------------------------------------------------

        source.commit()

        sources.append(source)

        print(f"Created {name}")

    # --------------------------------------------------------
    # SUMMARY
    # --------------------------------------------------------

    total_power = (
        len(sources) * p.LED_RADIANT_POWER_W
    )

    print("\nLED SOURCE SUMMARY")

    print(f"Number of LEDs: {len(sources)}")

    print(
        f"Power per LED: "
        f"{p.LED_RADIANT_POWER_W:.3f} W"
    )

    print(
        f"Total radiant power: "
        f"{total_power:.3f} W"
    )

    return sources