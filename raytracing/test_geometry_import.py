"""Test surface-only optical scene transfer."""
import argparse
from pathlib import Path
from ansys.speos.core import Project
from ansys.speos.core.launcher import launch_local_speos_rpc_server
from raytracing.geometry_import import import_optical_geometry
import parameters as p


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', required=True)
    parser.add_argument('--optical', default='optical_01')
    args = parser.parse_args()
    folder = Path(__file__).resolve().parents[1]/'output'/args.case/args.optical
    speos = launch_local_speos_rpc_server(version=p.SPEOS_VERSION)
    try:
        project = Project(speos=speos)
        geometry = import_optical_geometry(project, folder, p.OPTICAL_TOLERANCE,
            p.OPTICAL_ANGULAR_TOLERANCE, catalyst_mode=p.CATALYST_OPTICAL_MODE,
            include_gas=p.INCLUDE_GAS_BODY)
        print(f"Geometry transfer completed; {len(geometry['catalytic_faces'])} catalytic faces")
    finally:
        speos.close()


if __name__ == '__main__':
    main()
