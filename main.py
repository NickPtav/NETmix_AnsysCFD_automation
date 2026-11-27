"""NETmix CLI: generate, mesh, inspect or solve a selected reactor."""
import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
import parameters

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / 'output'
GEOMETRY_KEYS = ('N_ROWS','N_COLUMNS','D_PARALLEL','D_DIAGONAL','CHANNEL_WIDTH','H','HEIGHT','HORIZONTAL_CHANNELS','PORT_DIAMETER','PORT_LENGTH','PORT_SIDE','ILLUMINATION','CATALYST_THICKNESS','TOL')


def config(smoke):
    p = SimpleNamespace(**{k:v for k,v in vars(parameters).items() if k.isupper()})
    if smoke:
        p.N_ROWS = p.N_COLUMNS = 3
        p.CREATE_OPTICAL = False
        p.SHOW_VIEW = 'none'
        p.RUN_REACTION = False
        p.ITERATIONS = 30
    return p


def case_name(p):
    return f'NETMIX_{p.N_COLUMNS}_{p.N_ROWS}_{"CH" if p.HORIZONTAL_CHANNELS else "SH"}_{p.ILLUMINATION.upper()}'


def new_directory(parent, prefix):
    parent.mkdir(parents=True, exist_ok=True)
    n = 1
    while True:
        path = parent / f'{prefix}_{n:02d}'
        try:
            path.mkdir()
            return path
        except FileExistsError:
            n += 1


def read_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def locate_case(value):
    path = Path(value).expanduser()
    if not path.is_absolute() and not path.exists():
        path = OUTPUT / path
    return path.resolve()


def locate_mesh(value, case):
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = (case / path) if case is not None and (case / path).exists() else path
    path = path.resolve()
    return path / 'CFD.msh.h5' if path.is_dir() else path


def main():
    a = argparse.ArgumentParser(description=__doc__)
    a.add_argument('--stage', choices=['geometry','surface','mesh','inspect','solve','all'], default='geometry')
    a.add_argument('--case', help='Existing case folder name or path; for geometry/all, optional new case folder')
    a.add_argument('--mesh', help='Existing mesh folder or CFD.msh.h5 path (solve/inspect only)')
    a.add_argument('--smoke', action='store_true')
    a.add_argument('--reviewed', action='store_true')
    a.add_argument('--no-pause', action='store_true')
    a.add_argument('--list', action='store_true', help='List available geometries and meshes')
    args = a.parse_args()
    if args.list:
        for manifest in sorted(OUTPUT.glob('*/geometry.json')):
            print(manifest.parent.name)
            for m in sorted(manifest.parent.glob('*/CFD.msh.h5')):
                print('  ' + m.parent.name)
        return
    p = config(args.smoke)
    if args.mesh and args.stage not in ('inspect','solve'):
        a.error('--mesh is only for inspect/solve')
    case = locate_case(args.case) if args.case else None
    meshfile = locate_mesh(args.mesh, case) if args.mesh else None
    if meshfile is not None:
        if not meshfile.is_file():
            raise FileNotFoundError(meshfile)
        if case is None:
            case = meshfile.parent.parent
        if meshfile.parent.parent != case:
            raise ValueError('Selected mesh must belong to the selected case folder.')
    case = case or (OUTPUT / case_name(p))
    step = case / 'CFD.step'
    manifest = case / 'geometry.json'
    print('Case directory:', case, flush=True)
    if args.stage in ('geometry','all'):
        expected = {k:getattr(p,k) for k in GEOMETRY_KEYS}
        if manifest.is_file():
            if read_json(manifest)['geometry'] != expected:
                raise RuntimeError('Case name already used for different geometry parameters. Choose a new --case name.')
            if not step.is_file():
                raise FileNotFoundError(step)
            print('Existing matching geometry reused.', flush=True)
        else:
            if case.exists() and any(case.iterdir()):
                raise RuntimeError('Case folder is not empty and has no geometry manifest; choose a new name.')
            from geometry_setup import generate
            generate(p,case)
    if not manifest.is_file() or not step.is_file():
        raise FileNotFoundError(f'Missing geometry.json or CFD.step in {case}; generate geometry first.')
    # Existing geometry is authoritative; current parameters still control mesh and solver.
    for key, value in read_json(manifest)['geometry'].items():
        if key in GEOMETRY_KEYS:
            setattr(p,key,value)
    if args.stage in ('surface','mesh','all'):
        from meshing_setup import mesh
        if args.case and getattr(p,'CAD_INPUT_OVERRIDE',None):
            raise RuntimeError('Disable CAD_INPUT_OVERRIDE when selecting a saved case, or verify and mesh it separately.')
        meshing = new_directory(case,'surface' if args.stage=='surface' else 'mesh')
        meshfile = mesh(p,step,meshing,pause=False if args.no_pause else None,surface_only=args.stage=='surface')
    if args.stage in ('inspect','solve','all'):
        if meshfile is None:
            candidates = sorted(case.glob('*/CFD.msh.h5'))
            if len(candidates) != 1:
                raise RuntimeError('Select a mesh explicitly with --mesh. Available: ' + ', '.join(m.parent.name for m in candidates))
            meshfile = candidates[0]
        meshfile = Path(meshfile).resolve()
        meshing = meshfile.parent
        info = meshing / 'mesh_info.json'
        if not meshfile.is_file() or not info.is_file() or read_json(info).get('step_sha256') != hashlib.sha256(step.read_bytes()).hexdigest():
            raise RuntimeError('Mesh provenance missing or geometry changed; rerun --stage mesh.')
        from fluent_setup import run
        solve = args.stage in ('solve','all')
        out = new_directory(meshing,'solve' if solve else 'inspect')
        print('Selected mesh:',meshfile,flush=True)
        run(p,meshfile,manifest,out,solve=solve,reviewed=args.reviewed)


if __name__ == '__main__':
    main()
