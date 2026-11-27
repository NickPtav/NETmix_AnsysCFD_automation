"""
NETmix automated Speos simulation controller.

Responsibilities:
    1. Launch Speos RPC server.
    2. Import optical geometry.
    3. Configure optical materials.
    4. Configure LED sources.
    5. Configure irradiance sensor.
    6. Configure direct simulation.
    7. Export and compute simulation.
"""

import argparse
import json
from pathlib import Path

import parameters as p

from ansys.speos.core import Project

from ansys.speos.core.launcher import (
    launch_local_speos_rpc_server
)

from raytracing.geometry_import import (
    import_optical_geometry
)

from raytracing.materials import configure_materials
from raytracing.sources import configure_sources
from raytracing.sensors import configure_sensor
from raytracing.simulation import configure_simulation


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output"


# ============================================================
# OUTPUT DIRECTORY
# ============================================================

def create_output_directory(optical_dir):

    index = 1

    while True:

        output_dir = (
            optical_dir / f"raytracing_{index:02d}"
        )

        if not output_dir.exists():

            output_dir.mkdir(parents=True)

            return output_dir

        index += 1


# ============================================================
# MAIN SPEOS WORKFLOW
# ============================================================

def run_speos(optical_dir, smoke=False, setup_only=False):

    optical_dir = Path(optical_dir).resolve()

    if not optical_dir.is_dir():

        raise FileNotFoundError(optical_dir)

    input_dir = Path(p.SPEOS_INPUT_DIR).resolve()

    if not input_dir.is_dir():

        raise FileNotFoundError(input_dir)

    output_dir = create_output_directory(optical_dir)

    speos = None

    try:

        # ----------------------------------------------------
        # 1. LAUNCH SPEOS
        # ----------------------------------------------------

        print("\n[1/7] Launching Speos...")

        speos = launch_local_speos_rpc_server(
            version=p.SPEOS_VERSION
        )

        project = Project(speos=speos)

        # ----------------------------------------------------
        # 2. IMPORT GEOMETRY
        # ----------------------------------------------------

        print("\n[2/7] Importing optical geometry...")

        geometry = import_optical_geometry(
            project=project,
            optical_dir=optical_dir,
            tolerance=p.OPTICAL_TOLERANCE,
            angular_tolerance=p.OPTICAL_ANGULAR_TOLERANCE,
            catalyst_mode=p.CATALYST_OPTICAL_MODE,
            include_gas=p.INCLUDE_GAS_BODY
        )

        catalytic_faces = geometry["catalytic_faces"]

        catalyst_bodies = []

        if "catalyst" in geometry:

            catalyst_bodies.append(
                geometry["catalyst"]["body"].geo_path
            )

        # ----------------------------------------------------
        # 3. OPTICAL MATERIALS
        # ----------------------------------------------------

        print("\n[3/7] Configuring optical materials...")

        materials = configure_materials(
            project=project,
            p=p,
            metal_bodies=[
                geometry["metal"]["body"].geo_path
            ],
            catalyst_bodies=catalyst_bodies,
            glass_bodies=[
                geometry["glass"]["body"].geo_path
            ],
            input_dir=input_dir,
            catalytic_faces=[
                face.geo_path
                for face in catalytic_faces
            ]
        )

        # ----------------------------------------------------
        # 4. LED SOURCES
        # ----------------------------------------------------

        print("\n[4/7] Configuring LED sources...")

        for led in geometry["leds"]:

            # Right-handed coordinate system:
            # local Z points towards the reactor (-Z).

            led["axis_system"] = [
                *led["center_mm"],
                1, 0, 0,
                0, -1, 0,
                0, 0, -1
            ]

        sources = configure_sources(
            project=project,
            p=p,
            led_faces=geometry["leds"],
            input_dir=input_dir
        )

        # ----------------------------------------------------
        # 5. IRRADIANCE SENSOR
        # ----------------------------------------------------

        print("\n[5/7] Configuring irradiance sensor...")

        sensor = configure_sensor(
            project=project,
            p=p,
            catalytic_faces=[
                face.geo_path
                for face in catalytic_faces
            ]
        )

        # ----------------------------------------------------
        # 6. DIRECT SIMULATION
        # ----------------------------------------------------

        print("\n[6/7] Configuring direct simulation...")

        simulation = configure_simulation(
            project=project,
            p=p,
            sources=sources,
            sensor=sensor,
            smoke=smoke
        )

        # ----------------------------------------------------
        # SAVE SIMULATION SETTINGS
        # ----------------------------------------------------

        settings = {
            "speos_version": p.SPEOS_VERSION,
            "backend": p.SPEOS_BACKEND,
            "threads": p.SPEOS_THREADS,
            "catalyst_mode": p.CATALYST_OPTICAL_MODE,
            "include_gas": p.INCLUDE_GAS_BODY,
            "n_leds": len(sources),
            "power_per_led_W": p.LED_RADIANT_POWER_W,
            "total_radiant_power_W":
                len(sources) * p.LED_RADIANT_POWER_W,
            "n_catalytic_faces": len(catalytic_faces),
            "n_rays": (
                p.SPEOS_TEST_RAYS
                if smoke
                else p.SPEOS_N_RAYS
            ),
            "optical_tolerance_mm": p.OPTICAL_TOLERANCE,
            "angular_tolerance_rad":
                p.OPTICAL_ANGULAR_TOLERANCE
        }

        with open(
            output_dir / "simulation_settings.json",
            "w",
            encoding="utf-8"
        ) as file:

            json.dump(settings, file, indent=4)

        # ----------------------------------------------------
        # EXPORT CONFIGURED SIMULATION
        # ----------------------------------------------------

        print("\nExporting Speos simulation...")

        simulation.export(output_dir)

        if setup_only:

            print("\nSetup completed successfully.")
            print(f"Output: {output_dir}")

            return

        # ----------------------------------------------------
        # 7. COMPUTE SIMULATION
        # ----------------------------------------------------

        print("\n[7/7] Running ray tracing...")

        backend = p.SPEOS_BACKEND.upper()

        if backend == "CPU":

            results = simulation.compute_CPU(
                threads_number=p.SPEOS_THREADS,
                export_vtp=True
            )

        elif backend == "GPU":

            results = simulation.compute_GPU()

        else:

            raise ValueError(
                "SPEOS_BACKEND must be CPU or GPU."
            )

        print("\nSpeos computation returned:")
        print(results)

        print(f"\nOutput directory: {output_dir}")

    finally:

        if speos is not None:

            speos.close()

            print("\nSpeos session closed.")


# ============================================================
# COMMAND LINE INTERFACE
# ============================================================

def main():

    parser = argparse.ArgumentParser(
        description="NETmix automated Speos simulation"
    )

    parser.add_argument(
        "--case",
        required=True,
        help="Existing NETmix case directory"
    )

    parser.add_argument(
        "--optical",
        default="optical_01",
        help="Optical geometry directory"
    )

    parser.add_argument(
        "--smoke",
        action="store_true",
        help="Run with a reduced number of rays"
    )

    parser.add_argument(
        "--setup-only",
        action="store_true",
        help="Configure and export without computation"
    )

    args = parser.parse_args()

    optical_dir = (
        OUTPUT
        / args.case
        / args.optical
    )

    run_speos(
        optical_dir=optical_dir,
        smoke=args.smoke,
        setup_only=args.setup_only
    )


if __name__ == "__main__":

    main()