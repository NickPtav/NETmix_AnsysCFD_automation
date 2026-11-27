"""Run an explicit CSV list of NETmix geometries, meshes and simulations.
Place beside the updated main.py. No edits to parameters.py are made.
"""
import argparse
import csv
import hashlib
import json
import math
import re
import traceback
from datetime import datetime
from pathlib import Path

from main import (ROOT, OUTPUT, GEOMETRY_KEYS, config, case_name,
                  new_directory, read_json)

REQUIRED = ('N_ROWS', 'N_COLUMNS', 'CHANNEL_WIDTH', 'ILLUMINATION', 'HORIZONTAL_CHANNELS')


def read_cases(path):
    cases = []
    seen = set()
    with path.open(newline='', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)
        if not set(REQUIRED).issubset(reader.fieldnames or []):
            raise ValueError('CSV must contain: ' + ', '.join(REQUIRED))
        for line, row in enumerate(reader, 2):
            if not any(row.values()):
                continue
            p = config(False)
            for key in ('N_ROWS', 'N_COLUMNS'):
                value = int(row[key])
                if value < 3 or value % 2 == 0:
                    raise ValueError(f'CSV line {line}: {key} must be odd and >= 3')
                setattr(p, key, value)
            p.CHANNEL_WIDTH = float(row['CHANNEL_WIDTH'])
            if not math.isfinite(p.CHANNEL_WIDTH) or not 0 < p.CHANNEL_WIDTH < min(p.D_PARALLEL, p.D_DIAGONAL):
                raise ValueError(f'CSV line {line}: invalid CHANNEL_WIDTH')
            p.ILLUMINATION = row['ILLUMINATION'].strip().upper()
            if p.ILLUMINATION not in ('FSI', 'BSI'):
                raise ValueError(f'CSV line {line}: use FSI or BSI')
            ch = row['HORIZONTAL_CHANNELS'].strip().lower()
            if ch not in ('true', 'false', '1', '0', 'ch', 'sh'):
                raise ValueError(f'CSV line {line}: use True/False or CH/SH')
            p.HORIZONTAL_CHANNELS = ch in ('true', '1', 'ch')
            name = (row.get('CASE') or '').strip() or case_name(p)
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', name):
                raise ValueError(f'CSV line {line}: invalid CASE name')
            if name.casefold() in seen:
                raise ValueError(f'Duplicate CASE {name}; give different widths unique CASE names')
            seen.add(name.casefold())
            selected = (row.get('MESH') or '').strip()
            if selected and not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]*', selected):
                raise ValueError(f'CSV line {line}: MESH must be a mesh folder name')
            p.PAUSE_AFTER_SURFACE = False
            p.REQUIRE_ZONE_REVIEW = False
            p.KEEP_GUI_ON_ERROR = False
            p.SHOW_VIEW = 'none'
            if getattr(p, 'CAD_INPUT_OVERRIDE', None) or getattr(p, 'ZONE_MAP_FILE', None):
                raise ValueError('Disable CAD_INPUT_OVERRIDE and ZONE_MAP_FILE for a multi-geometry batch')
            if p.RUN_REACTION and p.IRRADIANCE_MODE == 'profile':
                raise ValueError('Batch profile mode needs a separate profile per case; use fixed mode for now')
            cases.append({'name': name, 'p': p, 'case': OUTPUT / name,
                          'selected': selected, 'mesh': None, 'failed': False})
    if not cases:
        raise ValueError('No cases in CSV')
    return cases


def verify_geometry(item, create=False):
    p, case = item['p'], item['case']
    manifest, step = case / 'geometry.json', case / 'CFD.step'
    expected = {key: getattr(p, key) for key in GEOMETRY_KEYS}
    if not manifest.is_file():
        if not create:
            raise FileNotFoundError(f'{manifest}; run geometry stage first')
        if case.exists() and any(case.iterdir()):
            raise RuntimeError(f'Incomplete nonempty case {case}; inspect it or choose another CASE name')
        from geometry_setup import generate
        generate(p, case)
    if not step.is_file():
        raise FileNotFoundError(step)
    if read_json(manifest)['geometry'] != expected:
        raise RuntimeError(f'{case.name}: saved geometry differs from CSV/current fixed parameters; use a different CASE or restore the original inputs')
    return step, manifest


def verify_mesh(meshfile, step):
    meshfile = Path(meshfile).resolve()
    info = meshfile.parent / 'mesh_info.json'
    if not meshfile.is_file() or not info.is_file():
        raise FileNotFoundError(f'Missing mesh or mesh_info.json: {meshfile}')
    if read_json(info).get('step_sha256') != hashlib.sha256(step.read_bytes()).hexdigest():
        raise RuntimeError(f'Mesh provenance mismatch: {meshfile}')
    return meshfile


def execute(item, stage):
    p, case = item['p'], item['case']
    step, manifest = verify_geometry(item, create=stage == 'geometry')
    if stage == 'geometry':
        return str(step)
    if stage == 'mesh':
        from meshing_setup import mesh
        out = new_directory(case, 'mesh')
        result = mesh(p, step, out, pause=False, surface_only=False)
        item['mesh'] = verify_mesh(result, step)
        return str(item['mesh'])
    if stage == 'solve':
        from fluent_setup import run
        chosen = item['mesh']
        if chosen is None:
            if item['selected']:
                chosen = case / item['selected'] / 'CFD.msh.h5'
            else:
                candidates = sorted(case.glob('mesh_*/CFD.msh.h5'))
                if len(candidates) != 1:
                    raise RuntimeError(f'{case.name}: expected one mesh; set MESH in CSV. Available: {[m.parent.name for m in candidates]}')
                chosen = candidates[0]
        chosen = verify_mesh(chosen, step)
        item['mesh'] = chosen
        out = new_directory(chosen.parent, 'solve')
        run(p, chosen, manifest, out, solve=True, reviewed=True)
        if not (out / 'NETmix.cas.h5').is_file() or not (out / 'NETmix.dat.h5').is_file():
            raise RuntimeError(f'Solver returned but expected case/data files are missing in {out}')
        return str(out)

        raise ValueError(stage)


# ============================================================
# MAIN BATCH CONTROLLER
# ============================================================

def main():

    # --------------------------------------------------------
    # COMMAND-LINE ARGUMENTS
    # --------------------------------------------------------

    parser = argparse.ArgumentParser(
        description='NETmix automated batch simulations'
    )

    parser.add_argument(
        '--file',
        type=Path,
        default=ROOT / 'batch_cases.csv',
        help='CSV file containing reactor configurations'
    )

    parser.add_argument(
        '--stage',
        choices=['geometry', 'mesh', 'solve', 'all'],
        default='all',
        help='Workflow stage to execute'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Display configurations without executing simulations'
    )

    parser.add_argument(
        '--stop-on-error',
        action='store_true',
        help='Stop batch execution if a case fails'
    )

    args = parser.parse_args()

    # --------------------------------------------------------
    # READ BATCH CONFIGURATIONS
    # --------------------------------------------------------

    csv_path = args.file.resolve()

    print("\n" + "=" * 70)
    print("NETMIX BATCH CONTROLLER")
    print("=" * 70)

    print(f"\nInput file: {csv_path}")

    cases = read_cases(csv_path)

    stages = (
        ['geometry', 'mesh', 'solve']
        if args.stage == 'all'
        else [args.stage]
    )

    print(f"Number of cases: {len(cases)}")
    print(f"Requested stages: {', '.join(stages)}")

    # --------------------------------------------------------
    # DISPLAY CONFIGURATIONS
    # --------------------------------------------------------

    print("\nREACTOR CONFIGURATIONS")
    print("-" * 70)

    for i, item in enumerate(cases, start=1):

        p = item['p']

        channels = (
            'CH' if p.HORIZONTAL_CHANNELS else 'SH'
        )

        print(
            f"{i:02d}. {item['name']} | "
            f"Rows={p.N_ROWS} | "
            f"Columns={p.N_COLUMNS} | "
            f"Width={p.CHANNEL_WIDTH} mm | "
            f"{channels} | "
            f"{p.ILLUMINATION}"
        )

    # --------------------------------------------------------
    # DRY RUN
    # --------------------------------------------------------

    if args.dry_run:

        print("\nDry run completed successfully.")
        print("No geometries or simulations were generated.")

        return 0

    # --------------------------------------------------------
    # CREATE BATCH OUTPUT DIRECTORY
    # --------------------------------------------------------

    OUTPUT.mkdir(parents=True, exist_ok=True)

    batch_dir = new_directory(OUTPUT, 'batch')

    print(f"\nBatch output directory: {batch_dir}")

    start_time = datetime.now()

    # --------------------------------------------------------
    # SAVE BATCH INPUTS
    # --------------------------------------------------------

    batch_inputs = {
        'input_file': str(csv_path),
        'start_time': start_time.isoformat(),
        'stages': stages,
        'cases': []
    }

    for item in cases:

        p = item['p']

        batch_inputs['cases'].append({
            'case': item['name'],
            'geometry': {
                key: getattr(p, key)
                for key in GEOMETRY_KEYS
            },
            'selected_mesh': item['selected']
        })

    (batch_dir / 'batch_inputs.json').write_text(
        json.dumps(
            batch_inputs,
            indent=2,
            default=str
        ),
        encoding='utf-8'
    )

    # --------------------------------------------------------
    # INITIALIZE SUMMARY
    # --------------------------------------------------------

    summary = []

    for item in cases:

        summary.append({
            'case': item['name'],
            'geometry': (
                'Pending' if 'geometry' in stages
                else 'Not requested'
            ),
            'mesh': (
                'Pending' if 'mesh' in stages
                else 'Not requested'
            ),
            'solve': (
                'Pending' if 'solve' in stages
                else 'Not requested'
            ),
            'geometry_path': '',
            'mesh_path': '',
            'solve_path': '',
            'error': ''
        })

    def save_summary():

        # JSON summary

        (batch_dir / 'batch_summary.json').write_text(
            json.dumps(summary, indent=2),
            encoding='utf-8'
        )

        # CSV summary

        with (batch_dir / 'batch_summary.csv').open(
            'w',
            newline='',
            encoding='utf-8'
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=list(summary[0].keys())
            )

            writer.writeheader()
            writer.writerows(summary)

    save_summary()

    # --------------------------------------------------------
    # EXECUTE BATCH
    # --------------------------------------------------------

    stop_batch = False

    for stage in stages:

        print("\n" + "=" * 70)
        print(f"BATCH STAGE: {stage.upper()}")
        print("=" * 70)

        for i, item in enumerate(cases):

            row = summary[i]

            if item['failed']:

                row[stage] = 'Skipped'
                save_summary()

                continue

            print(
                f"\n[{i + 1}/{len(cases)}] "
                f"{item['name']}",
                flush=True
            )

            row[stage] = 'Running'
            save_summary()

            try:

                result_path = execute(item, stage)

                row[stage] = 'Completed'

                row[f'{stage}_path'] = result_path

                print(
                    f"{stage.upper()} COMPLETED",
                    flush=True
                )

            except Exception as exc:

                item['failed'] = True

                row[stage] = 'Failed'
                row['error'] = str(exc)

                print(
                    f"\nERROR: {item['name']}",
                    flush=True
                )

                traceback.print_exc()

                # Save individual error log

                error_file = (
                    batch_dir
                    / f"{item['name']}_{stage}_error.txt"
                )

                error_file.write_text(
                    traceback.format_exc(),
                    encoding='utf-8'
                )

                if args.stop_on_error:

                    stop_batch = True

            finally:

                save_summary()

            if stop_batch:
                break

        if stop_batch:
            break

    # --------------------------------------------------------
    # UPDATE UNFINISHED STAGES
    # --------------------------------------------------------

    for row in summary:

        for stage in stages:

            if row[stage] == 'Pending':

                row[stage] = 'Skipped'

    save_summary()

    # --------------------------------------------------------
    # FINAL EXECUTION SUMMARY
    # --------------------------------------------------------

    elapsed = (
        datetime.now() - start_time
    ).total_seconds()

    successful = sum(
        all(row[stage] == 'Completed' for stage in stages)
        for row in summary
    )

    failed = sum(
        any(row[stage] == 'Failed' for stage in stages)
        for row in summary
    )

    skipped = len(cases) - successful - failed

    print("\n" + "=" * 70)
    print("BATCH EXECUTION FINISHED")
    print("=" * 70)

    print(f"Total cases:      {len(cases)}")
    print(f"Successful cases: {successful}")
    print(f"Failed cases:     {failed}")
    print(f"Skipped cases:    {skipped}")
    print(f"Total time:       {elapsed / 60:.2f} minutes")

    print(f"\nResults saved in:\n{batch_dir}")

    return 0 if successful == len(cases) else 1


# ============================================================
# SCRIPT ENTRY POINT
# ============================================================

if __name__ == '__main__':
    raise SystemExit(main())
