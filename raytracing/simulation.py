"""
NETmix direct ray-tracing simulation.

Configuration and execution of optical simulations
using the PySpeos API.
"""

from pathlib import Path

from ansys.speos.core.simulation import SimulationDirect


# ============================================================
# CONFIGURE DIRECT SIMULATION
# ============================================================

def configure_simulation(
    project,
    p,
    sources,
    sensor,
    smoke=False
):

    if not sources:
        raise ValueError("No optical sources defined.")

    if sensor is None:
        raise ValueError("No irradiance sensor defined.")

    # --------------------------------------------------------
    # CREATE SIMULATION
    # --------------------------------------------------------

    simulation = project.create_simulation(
        name=p.SPEOS_SIMULATION_NAME,
        feature_type=SimulationDirect
    )

    # --------------------------------------------------------
    # ASSIGN SOURCES
    # --------------------------------------------------------

    source_names = [
        f"LED_{i:03d}"
        for i in range(1, len(sources) + 1)
    ]

    simulation.source_paths = source_names

    # --------------------------------------------------------
    # ASSIGN SENSOR
    # --------------------------------------------------------

    simulation.sensor_paths = [
        p.SPEOS_SENSOR_NAME
    ]

    # --------------------------------------------------------
    # STOP CONDITIONS
    # --------------------------------------------------------

    n_rays = (
        p.SPEOS_TEST_RAYS
        if smoke
        else p.SPEOS_N_RAYS
    )

    simulation.stop_condition_rays_number = int(n_rays)

    # --------------------------------------------------------
    # PRINT CONFIGURATION
    # --------------------------------------------------------

    print("\nDIRECT SIMULATION CONFIGURATION")

    print(f"Simulation: {p.SPEOS_SIMULATION_NAME}")

    print(f"Number of sources: {len(source_names)}")

    print(f"Sources: {simulation.source_paths}")

    print(f"Sensors: {simulation.sensor_paths}")

    print(f"Number of rays: {n_rays:,}")

    print(f"Backend: {p.SPEOS_BACKEND}")

    # --------------------------------------------------------
    # COMMIT SIMULATION
    # --------------------------------------------------------

    simulation.commit()

    print("\nDirect simulation configured successfully.")

    return simulation


# ============================================================
# EXECUTE SIMULATION
# ============================================================

def run_simulation(
    simulation,
    p,
    output_dir
):

    output_dir = Path(output_dir).resolve()

    output_dir.mkdir(
        parents=True,
        exist_ok=True
    )

    # --------------------------------------------------------
    # EXPORT SIMULATION
    # --------------------------------------------------------

    print("Exporting Speos simulation...")

    simulation.export(output_dir)

    # --------------------------------------------------------
    # COMPUTATION
    # --------------------------------------------------------

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

    print("Ray-tracing computation completed.")

    return results