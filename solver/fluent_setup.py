"""Load mesh, reconstruct boundary groups, and optionally configure/run solver."""
import json
import shutil
from pathlib import Path
from time import perf_counter

from meshing.meshing_setup import launch

from solver.zone_mapping import (
    settings,
    map_zones,
    apply_zone_types
)

from solver.legacy_physics import configure_materials

from postprocessing.post_processing import post_process

ROOT = Path(__file__).resolve().parents[1]

UDF_DIR = ROOT / "solver" / "udfs"

def prepare_udf(solver, p, root, out):

    # ============================================================
    # SELECT UDF SOURCE
    # ============================================================

    source = UDF_DIR / 'UDF_tce.c'

    if p.IRRADIANCE_MODE == 'profile':

        source = Path(
            p.PROFILE_UDF_SOURCE or ROOT / 'UDF_tce_profile.c'
        ).resolve()

    if not source.is_file():

        raise FileNotFoundError(source)

    # ============================================================
    # COPY UDF TO SIMULATION DIRECTORY
    # ============================================================

    local = out / source.name

    if source.resolve() != local.resolve():

        shutil.copy2(source, local)

    print(f"\nUDF source: {local}", flush=True)

    # ============================================================
    # COMPILE UDF
    # ============================================================

    if not p.COMPILE_UDF:

        raise ValueError(
            'Fresh run requires UDF compilation; '
            'old DLLs are not portable.'
        )

    udf = root.setup.user_defined

    print("\nCompiling UDF...", flush=True)

    udf.compiled_udf(
        library_name=p.UDF_LIBRARY,
        source_files=[local.name],
        header_files=[]
    )

    print("UDF compilation completed.", flush=True)

    # ============================================================
    # LOAD UDF LIBRARY
    # ============================================================

    print("\nLoading UDF library...", flush=True)

    udf.load(
        udf_library_name=p.UDF_LIBRARY
    )

    print("UDF library loaded.", flush=True)

    # ============================================================
    # HOOK SURFACE REACTION RATE
    # ============================================================

    function_name = (
        f"{p.UDF_FUNCTION_NAME}::{p.UDF_LIBRARY}"
    )

    hooks = udf.function_hooks

    print("\nAvailable surface reaction functions:")

    available = (
        hooks.surface_reaction_rate.allowed_values()
    )

    print(available, flush=True)

    if function_name not in available:

        raise RuntimeError(
            f'UDF function {function_name} not available. '
            f'Available functions: {available}'
        )

    hooks.surface_reaction_rate = function_name

    # ============================================================
    # VERIFY UDF ASSIGNMENT
    # ============================================================

    assigned = hooks.surface_reaction_rate()

    if assigned != function_name:

        raise RuntimeError(
            f'UDF hook assignment failed. '
            f'Expected {function_name}, got {assigned}'
        )

    print(
        f"\nSurface reaction UDF assigned: {assigned}",
        flush=True
    )

def configure_solver(solver,p,groups,out):
    root=settings(solver); setup=root.setup; bc=setup.boundary_conditions
    setup.models.viscous.model='laminar'
    setup.models.energy.enabled=False
    # Hydrodynamic-only first pass avoids using unverified legacy TCE properties.
    if p.RUN_REACTION:
        if not p.ACCEPT_LEGACY_PHYSICS:
            raise RuntimeError('Review legacy_physics.py and original reaction stoichiometry; set ACCEPT_LEGACY_PHYSICS=True explicitly.')
        setup.models.species.model.option='species-transport'
        setup.models.species.reactions.enable_volumetric_reactions=True
        setup.models.species.reactions.enable_wall_surface=True
        setup.models.species.wall_surface_options.heat_of_surface_reactions=False
        setup.models.species.options.diffusion_energy_source=False
        configure_materials(solver,root)
        fluids=setup.cell_zone_conditions.fluid.get_object_names()
        if len(fluids)!=1: raise RuntimeError(f'Expected one fluid cell zone; got {fluids}')
        # Retain old reaction registration, but disable volumetric reaction in fluid.
        fluid=setup.cell_zone_conditions.fluid[fluids[0]]
        fluid.general.material='mixture-template'
        fluid.reaction.react=False
    for name in groups['inlet']:
        zone=bc.velocity_inlet[name]
        zone.momentum.velocity_specification_method='Magnitude, Normal to Boundary'
        zone.momentum.velocity={'option':'value','value':p.INLET_VELOCITY}
        if p.RUN_REACTION:
            zone.species.specify_species_in_mole_fractions=True
            zone.species.mf['tce']={'option':'value','value':p.TCE_MOLE_FRACTION}
            zone.species.mf['water-vapor']={'option':'value','value':p.WATER_MOLE_FRACTION}
            # Energy is disabled: only assign temperature if available in current setup.
    for name in groups['outlet']:
        zone=bc.pressure_outlet[name]
        zone.momentum.gauge_pressure={'option':'value','value':p.OUTLET_GAUGE_PRESSURE_PA}
        if p.RUN_REACTION:
            # Match inlet species for reverse flow; confirm in GUI if reverse flow occurs.
            zone.species.specify_species_in_mole_fractions=True
            zone.species.mf['tce']={'option':'value','value':p.TCE_MOLE_FRACTION}
            zone.species.mf['water-vapor']={'option':'value','value':p.WATER_MOLE_FRACTION}
    if p.RUN_REACTION:
        for name in groups['catalytic_wall']: bc.wall[name].species.react=True
        for name in groups['non_catalytic_wall']: bc.wall[name].species.react=False
    root.solution.methods.p_v_coupling.flow_scheme='SIMPLE'
    if p.RUN_REACTION:
        if p.IRRADIANCE_MODE == 'profile':

            source = Path(
                p.PROFILE_UDF_SOURCE
                or UDF_DIR / 'UDF_tce_profile.c'
            ).resolve()
            if not profile.is_file(): raise FileNotFoundError(profile)
            root.file.read_profile(file_name=str(profile))
            solver.tui.define.user_defined.user_defined_scalars('1')
            for name in groups['catalytic_wall']:
                wall=bc.wall[name]
                wall.uds.uds_bc['User Scalar 0']='Specified Value'
                wall.uds.uds['User Scalar 0']={'option':'profile','profile_name':p.PROFILE_NAME,'field_name':p.PROFILE_FIELD}
        elif p.IRRADIANCE_MODE!='fixed': raise ValueError('IRRADIANCE_MODE must be fixed or profile.')
        
        prepare_udf(solver,p,root,out)
    # Named residual controls avoid assuming an energy equation is active.
    eqs=root.solution.monitor.residual.equations
    for name in eqs.get_object_names(): eqs[name].absolute_criteria=1e-8
    reports=root.solution.report_definitions.surface
    for name,field,surfaces in [('inlet_pressure_avg','total-pressure',groups['inlet']),('outlet_pressure_avg','total-pressure',groups['outlet'])]:
        reports.create(name); reports[name].set_state({'report_type':'surface-areaavg','field':field,'surface_names':surfaces})
    if p.RUN_REACTION:
        for name,surfaces in [('inlet_tce_molefraction_avg',groups['inlet']),('outlet_tce_molefraction_avg',groups['outlet'])]:
            reports.create(name); reports[name].set_state({'report_type':'surface-areaavg','field':'molef-tce','surface_names':surfaces})
    # ============================================================
    # SOLUTION INITIALIZATION
    # ============================================================

    root.solution.initialization.hybrid_initialize()

    # ============================================================
    # RUN SIMULATION
    # ============================================================

    print("\nStarting CFD simulation...", flush=True)

    start_time = perf_counter()

    root.solution.run_calculation.iterate(
        iter_count=p.ITERATIONS
    )

    elapsed_s = perf_counter() - start_time

    print(
        f"\nSimulation time: {elapsed_s:.2f} seconds",
        flush=True
    )

    # ============================================================
    # SAVE CASE AND DATA
    # ============================================================

    root.file.write(
        file_type='case-data',
        file_name=str(out / 'NETmix.cas.h5')
    )

    print("Case and data files saved.", flush=True)

    return elapsed_s

def run(p, mesh_path, manifest_path, out,
        solve=False, reviewed=False):

    # ============================================================
    # PREPARE DIRECTORIES
    # ============================================================

    mesh_path = Path(mesh_path).resolve()

    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=True)

    if not mesh_path.is_file():
        raise FileNotFoundError(mesh_path)

    manifest = json.loads(
        Path(manifest_path).read_text(encoding='utf-8')
    )

    # ============================================================
    # LAUNCH FLUENT
    # ============================================================

    solver = launch(p, 'solver', out)

    ok = False

    try:

        root = settings(solver)

        # --------------------------------------------------------
        # READ AND CHECK MESH
        # --------------------------------------------------------

        root.file.read_mesh(
            file_name=str(mesh_path)
        )

        solver.mesh.check()
        solver.mesh.quality()

        # --------------------------------------------------------
        # VERIFY FLUID DOMAIN
        # --------------------------------------------------------

        fluids = (
            root.setup.cell_zone_conditions
            .fluid.get_object_names()
        )

        if len(fluids) != 1:

            raise RuntimeError(
                f'Expected exactly one fluid region, found {fluids}'
            )

        # --------------------------------------------------------
        # AUTOMATIC BOUNDARY CLASSIFICATION
        # --------------------------------------------------------

        groups = map_zones(
            solver,
            manifest,
            out,
            p.ZONE_MAP_FILE
        )

        apply_zone_types(solver, groups)

        print(json.dumps(groups, indent=2))

        # ========================================================
        # SOLVER STAGE
        # ========================================================

        if solve:

            # ----------------------------------------------------
            # OPTIONAL BOUNDARY REVIEW
            # ----------------------------------------------------

            if p.REQUIRE_ZONE_REVIEW and not reviewed:

                if not p.SHOW_GUI:

                    raise RuntimeError(
                        'Review zone_mapping.json first, '
                        'then use --reviewed.'
                    )

                answer = input(
                    'Inspect mesh quality, boundary groups '
                    'and units in Fluent. '
                    'Type YES to continue: '
                )

                if answer != 'YES':

                    raise RuntimeError(
                        'Solver not approved.'
                    )

            # ----------------------------------------------------
            # CONFIGURE AND RUN SIMULATION
            # ----------------------------------------------------

            elapsed_s = configure_solver(
                solver,
                p,
                groups,
                out
            )

            # ----------------------------------------------------
            # AUTOMATIC POST-PROCESSING
            # ----------------------------------------------------

            if p.RUN_POST_PROCESSING:

                print("\n" + "=" * 60)
                print("STARTING POST-PROCESSING")
                print("=" * 60)

                post_process(
                    solver=solver,
                    groups=groups,
                    manifest=manifest,
                    output=out,
                    elapsed_s=elapsed_s,
                    mass_tol_pct=p.MASS_BALANCE_TOL_PCT,
                    area_tol_pct=p.BOUNDARY_AREA_TOL_PCT
                )

                print("\nPost-processing completed.")
                print(f"Results saved in: {out}")

        # ========================================================
        # INSPECTION STAGE
        # ========================================================

        else:

            root.file.write(
                file_type='case',
                file_name=str(out / 'inspection.cas.h5')
            )

            print(
                'Inspection case saved. '
                'Check actual boundary groups in '
                'zone_mapping.json and GUI.'
            )

            if p.SHOW_GUI:

                input(
                    'Press Enter to close inspection session. '
                )

        ok = True

    # ============================================================
    # ERROR REPORTING
    # ============================================================

    except Exception:

        import traceback

        print("\n" + "=" * 60)
        print("ERROR DURING FLUENT SOLVER STAGE")
        print("=" * 60)

        traceback.print_exc()

        raise

    # ============================================================
    # CLOSE FLUENT
    # ============================================================

    finally:

        if not ok and p.SHOW_GUI and p.KEEP_GUI_ON_ERROR:

            try:

                input(
                    'Solver stage stopped. '
                    'Inspect Fluent, then Enter to close. '
                )

            except (EOFError, KeyboardInterrupt):

                pass

        solver.exit()