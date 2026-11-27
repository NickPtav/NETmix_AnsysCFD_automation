"""Fluent Watertight Geometry workflow, adapted from original meshing_setup.py."""
from pathlib import Path
import json
import hashlib
import time

def launch(p, mode, cwd):

    import os
    from pathlib import Path
    import ansys.fluent.core as pyfluent

    # --------------------------------------------------------
    # ANSYS INSTALLATION
    # --------------------------------------------------------

    os.environ["AWP_ROOT261"] = p.ANSYS_ROOT

    fluent_exe = Path(p.FLUENT_PATH)

    if not fluent_exe.is_file():
        raise FileNotFoundError(
            f"Fluent executable not found:\n{fluent_exe}"
        )

    # --------------------------------------------------------
    # WORKING DIRECTORY
    # --------------------------------------------------------

    cwd = Path(cwd).resolve()
    cwd.mkdir(parents=True, exist_ok=True)

    # Verify working directory
    print(f"Fluent working directory: {cwd}", flush=True)

    if any(char.isspace() for char in str(cwd)):
        raise ValueError(
            f"Fluent working directory contains spaces: {cwd}"
        )

    # --------------------------------------------------------
    # LAUNCH FLUENT
    # --------------------------------------------------------

    print("\nLaunching Ansys Fluent")
    print(f"Version: {p.FLUENT_VERSION}")
    print(f"Mode: {mode}")
    print(f"Processors: {p.PROCESSORS}")
    print(f"Executable: {fluent_exe}")
    print(f"Working directory: {cwd}\n")

    session = pyfluent.launch_fluent(
        product_version=p.FLUENT_VERSION,
        fluent_path=str(fluent_exe),
        mode=mode,
        dimension=3,
        precision="double",
        processor_count=p.PROCESSORS,
        ui_mode="gui" if p.SHOW_GUI else "no_gui",
        cwd=str(cwd),
        start_timeout=180
    )

    return session

def task(w,name,arguments=None):
    print(f'Fluent meshing: {name}',flush=True)
    t=w.TaskObject[name]
    if arguments is not None: t.Arguments.set_state(arguments)
    result=t.Execute()
    if result is False: raise RuntimeError(f'Fluent task failed: {name}')
    return t

def mesh(p, step_path, output, pause=None, surface_only=False):
    step_path=Path(step_path).resolve(); output=Path(output).resolve()
    if not step_path.is_file() or step_path.suffix.lower() not in ('.step','.stp'):
        raise FileNotFoundError(f'Expected a CFD STEP file: {step_path}')
    if min(p.SURFACE_MAX_SIZE_MM,p.VOLUME_MAX_SIZE_MM)<=0: raise ValueError('Mesh sizes must be positive.')
    if p.VOLUME_METHOD not in ('polyhedra','multizone'): raise ValueError('Unknown mesh method')
    if p.VOLUME_METHOD=='multizone' and not p.MULTIZONE_REGION:
        raise ValueError('Set MULTIZONE_REGION to the exact imported region name; use polyhedra for first tests.')
    output.mkdir(parents=True,exist_ok=True)
    session=launch(p,'meshing',output)
    ok=False
    try:
        w=session.workflow
        w.InitializeWorkflow(WorkflowType='Watertight Geometry')
        session.meshing.GlobalSettings.LengthUnit.set_state('mm')
        session.meshing.GlobalSettings.AreaUnit.set_state('mm^2')
        session.meshing.GlobalSettings.VolumeUnit.set_state('mm^3')
        cad_path=Path(p.CAD_INPUT_OVERRIDE).expanduser().resolve() if p.CAD_INPUT_OVERRIDE else step_path
        if not cad_path.is_file(): raise FileNotFoundError(cad_path)
        args={'FileName':str(cad_path),'LengthUnit':'mm','FileFormat':'CAD'}
        if p.CAD_SEPARATION_MODE:
            args['ImportCadPreferences']={'ShowImportCadPreferences':True,'CISeparation':p.CAD_SEPARATION_MODE}
        task(w,'Import Geometry',args)
        w.TaskObject['Add Local Sizing'].AddChildToTask()
        task(w,'Add Local Sizing')
        task(w, 'Generate the Surface Mesh', {
            'CFDSurfaceMeshControls': {
                'MaxSize': p.SURFACE_MAX_SIZE_MM
            },
            'SeparationRequired': (
                'Yes' if p.SURFACE_SEPARATION_REQUIRED else 'No'
            ),
            'SeparationAngle': p.SURFACE_SEPARATION_ANGLE
        })
        describe=w.TaskObject['Describe Geometry']
        describe.Arguments.set_state({'Multizone':'Yes' if p.VOLUME_METHOD=='multizone' else 'No',
            'NonConformal':'No','SetupType':'The geometry consists of only fluid regions with no voids'})
        describe.UpdateChildTasks(SetupTypeChanged=True)
        task(w,'Describe Geometry')
        task(w,'Update Boundaries')
        task(w,'Update Regions')
        # Persist actual workflow data for diagnostics (not guessed SpaceClaim names).
        diagnostics={n:w.TaskObject[n].Arguments.get_state() for n in ('Update Boundaries','Update Regions')}
        (output/'meshing_zones.json').write_text(json.dumps(diagnostics,indent=2,default=str),encoding='utf-8')
        # ------------------------------------------------------------
        # INTERACTIVE MESHING CONTROL
        # ------------------------------------------------------------

        if surface_only or (
            p.PAUSE_AFTER_SURFACE if pause is None else pause
        ):

            print("\n" + "=" * 60)
            print("SURFACE MESH COMPLETED")
            print("=" * 60)

            print("\nInspect the geometry and boundaries in Fluent.")

            print("\nAvailable options:")
            print("[1] Generate volume mesh")
            print("[2] Close Fluent")

            while True:

                choice = input("\nSelect an option: ").strip()

                if choice == "1":

                    print("\nContinuing to volume mesh generation...")
                    break

                elif choice == "2":

                    print("\nClosing Fluent...")
                    ok = True
                    return None

                else:

                    print("Invalid option. Please select 1 or 2.")
        task(w,'Add Boundary Layers',{'AddChild':'no','BLControlName':'smooth-transition_1',
            'LocalPrismPreferences':{'Continuous':'Continuous'}})
        if p.VOLUME_METHOD=='multizone':
            # Some legacy releases add tasks automatically; insert only if absent.
            try: mz=w.TaskObject['Add MultiZone Controls']
            except Exception:
                w.TaskObject['Add Boundary Layers'].InsertNextTask(CommandName='AddMultiZoneControls',Select=True)
                mz=w.TaskObject['Add MultiZone Controls']
            try: w.TaskObject['Generate the MultiZone Mesh']
            except Exception: mz.InsertNextTask(CommandName='GenerateTheMultiZoneMesh',Select=True)
            r=p.MULTIZONE_REGION
            mz.Arguments.set_state({'CompleteRegionScope':[r],'ControlType':'Regions','FillWith':'Hex-Pave',
                'Intervals':p.MULTIZONE_INTERVALS,'LabelSourceList':p.MULTIZONE_SOURCE_LABELS,
                'MultiZName':'mz-region_1','RegionScope':[r],'SourceMethod':'Labels','UseSweepSize':'yes'})
            mz.AddChildAndUpdate(DeferUpdate=True)
            task(w,'Add MultiZone Controls')
            task(w,'Generate the MultiZone Mesh',{'RegionScope':[r]})
        else:
            task(w,'Generate the Volume Mesh',{'VolumeFill':'polyhedra','VolumeFillControls':{'TetPolyMaxCellLength':p.VOLUME_MAX_SIZE_MM},'ReMergeZones':'no'})
        meshfile = output / 'CFD.msh.h5'
        temporary = output / f'CFD_{time.time_ns()}.msh.h5'

        # Use forward slashes and explicitly quote the path
        mesh_path = temporary.resolve().as_posix()

        print(f"\nSaving volume mesh to: {mesh_path}", flush=True)

        session.tui.file.write_mesh(f'"{mesh_path}"')

        print("Mesh writing completed.", flush=True)
        if not temporary.is_file() or temporary.stat().st_size < 1024:
            raise RuntimeError('Mesh file missing or unexpectedly small.')
        temporary.replace(meshfile)
        (output/'mesh_info.json').write_text(json.dumps({'step_sha256':hashlib.sha256(step_path.read_bytes()).hexdigest(),'import_path':str(cad_path),'import_sha256':hashlib.sha256(cad_path.read_bytes()).hexdigest()},indent=2),encoding='utf-8')
        ok=True
        return meshfile
    finally:
        if not ok and p.SHOW_GUI and p.KEEP_GUI_ON_ERROR:
            print('Mesh stage failed. Inspect the Fluent GUI/transcript; close it manually if left open.')
            try: input('Press Enter to close this Fluent session (Ctrl+C to interrupt). ')
            except (KeyboardInterrupt,EOFError): pass
        session.exit()
