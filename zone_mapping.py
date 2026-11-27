"""Resolve Fluent face zones using actual mesh geometry, not imported names."""
import json
from pathlib import Path
import numpy as np

from ansys.fluent.core import (
    SurfaceFieldDataRequest,
    SurfaceDataType
)

GROUPS=('inlet','outlet','catalytic_wall','non_catalytic_wall')
TYPES={'inlet':'velocity-inlet','outlet':'pressure-outlet','catalytic_wall':'wall','non_catalytic_wall':'wall'}

def classify_centroids(points_m, geometry, tol_mm=0.002):
    """Each face centroid must belong to the same physical boundary group.
    Assumes unchanged CadQuery axes and Fluent coordinates in SI metres.
    """
    a=np.asarray(points_m,dtype=float).reshape(-1,3)*1000
    if not len(a) or not np.isfinite(a).all(): raise ValueError('Empty/non-finite face coordinates')
    h=geometry['HEIGHT']; L=geometry['PORT_LENGTH']; side=geometry['PORT_SIDE']; mode=geometry['ILLUMINATION'].upper()
    zend=h+L if side=='top' else -L
    last=(geometry['N_ROWS']-1)*geometry['H']/2
    x,z=a[:,0],a[:,2]
    end=np.isclose(z,zend,rtol=0,atol=tol_mm)
    inlet=end & (np.abs(x)<=geometry['PORT_DIAMETER']/2+tol_mm)
    outlet=end & (np.abs(x-last)<=geometry['PORT_DIAMETER']/2+tol_mm)
    if np.any(end & ~(inlet|outlet)): raise ValueError('Unexpected port end location')
    if np.any((z<min(0,zend)-tol_mm)|(z>max(h,zend)+tol_mm)): raise ValueError('Coordinates outside expected height; check STEP units')
    top=np.isclose(z,h,rtol=0,atol=tol_mm)
    bottom=np.isclose(z,0,rtol=0,atol=tol_mm)
    core_side=(z>tol_mm)&(z<h-tol_mm)
    catalytic=(top if mode=='BSI' else bottom|core_side)&~end
    noncat=~(inlet|outlet|catalytic)
    found=[g for g,mask in zip(GROUPS,(inlet,outlet,catalytic,noncat)) if np.any(mask)]
    if len(found)!=1: raise ValueError('Mixed physical regions in one zone: '+', '.join(found))
    return found[0]

def settings(solver):
    return getattr(solver,'settings',solver)

def get_field_data(solver):
    """
    Access the field data interface for PyFluent 0.43.1.
    """

    return solver.fields.field_data


def surface_array(fd, name, kind):
    """
    Retrieve surface face centroids or vertices
    using the current PyFluent API.

    Coordinates are returned in meters.
    """

    if kind == "centroid":

        data_type = SurfaceDataType.FacesCentroid
        attribute = "face_centroids"

    elif kind == "vertices":

        data_type = SurfaceDataType.Vertices
        attribute = "vertices"

    else:

        raise ValueError(
            f"Unsupported surface data type: {kind}"
        )

    # Create surface data request
    request = SurfaceFieldDataRequest(
        surfaces=[name],
        data_types=[data_type]
    )

    # Retrieve numerical data from Fluent
    response = fd.get_field_data(request)

    # Extract requested surface
    if name in response:

        surface = response[name]

    elif len(response) == 1:

        surface = next(iter(response.values()))

    else:

        raise RuntimeError(
            f"Unexpected response for surface: {name}"
        )

    # Extract coordinates
    data = getattr(surface, attribute)

    if data is None:

        raise ValueError(
            f"No {kind} data returned for {name}"
        )

    result = np.asarray(
        data,
        dtype=float
    ).reshape(-1, 3)

    # Validate numerical coordinates
    if not len(result) or not np.isfinite(result).all():

        raise ValueError(
            f"Invalid {kind} coordinates for {name}"
        )

    return result

def map_zones(solver, manifest, output, manual=None):

    print(
        "\nStarting automatic boundary mapping...",
        flush=True
    )

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)

    g = manifest["geometry"]

    print("[1] Geometry manifest loaded.", flush=True)

    bc = settings(solver).setup.boundary_conditions

    print("[2] Boundary conditions accessed.", flush=True)

    # Current PyFluent field data API
    fd = get_field_data(solver)

    print("[3] Field data interface accessed.", flush=True)

    # Retrieve available surface names
    surface_names = fd.surfaces.allowed_values()

    print("[4] Surface information retrieved.", flush=True)

    print(
        f"Available surfaces: {len(surface_names)}",
        flush=True
    )

    # Save available surface information
    info = {
        "surface_names": list(surface_names)
    }

    (output / "fluent_surfaces.json").write_text(
        json.dumps(info, indent=2, default=str),
        encoding="utf-8"
    )

    print("[5] Surface information saved.", flush=True)

    # Enumerate actual exterior zones
    actual = {}
    for kind in ('wall','velocity_inlet','pressure_outlet','mass_flow_inlet','pressure_inlet','outflow','symmetry','inlet_vent','outlet_vent','far_field','pressure_far_field','interface','periodic'):
        obj=getattr(bc,kind,None)
        if obj is not None:
            for name in obj.get_object_names(): actual[name]=kind
    print(
        f"[6] Number of exterior zones: {len(actual)}",
        flush=True
    )

    for name, kind in actual.items():
        print(f"    {name}: {kind}")        
    if not actual: raise RuntimeError('No exterior zones returned by Fluent')
    # Detect unsupported zone kinds reported as solver boundaries, rather than silently ignore.
    permitted={'wall','velocity_inlet','pressure_outlet','mass_flow_inlet','pressure_inlet','outflow'}
    unsupported={k:v for k,v in actual.items() if v not in permitted}
    if unsupported: raise RuntimeError(f'Unexpected exterior zones: {unsupported}')
    groups={g:[] for g in GROUPS}; problems={}; rows=[]; lows=[]; highs=[]
    for name, kind in sorted(actual.items()):
        print(f"\nClassifying zone: {name}", flush=True)
        try:

            pts = surface_array(fd, name, 'centroid')

            print(
                f"  Face centroids retrieved: {len(pts)}",
                flush=True
            )

            vs = surface_array(fd, name, 'vertices') * 1000

            print(
                f"  Vertices retrieved: {len(vs)}",
                flush=True
            )
            lows.append(vs.min(axis=0)); highs.append(vs.max(axis=0))
            group=classify_centroids(pts,g)
            print(f"  Assigned group: {group}", flush=True)
            groups[group].append(name)
            rows.append({'zone':name,'old_type':kind,'group':group,'mesh_faces':len(pts),
                         'bounds_mm':[vs.min(axis=0).tolist(),vs.max(axis=0).tolist()]})
        except Exception as e:
            problems[name] = str(e)

            print(
                f"  Classification failed: {type(e).__name__}: {e}",
                flush=True
            )
    report={'groups':groups,'zones':rows,'unresolved':problems,'cad_areas_mm2':manifest['group_areas_mm2']}
    if lows:
        lo=np.min(lows,axis=0); hi=np.max(highs,axis=0)
        report['mesh_bounds_mm']=[lo.tolist(),hi.tolist()]
        b=manifest['bounds_mm']; expected=np.array([[b[0],b[2],b[4]],[b[1],b[3],b[5]]])
        if not problems and not np.allclose([lo,hi],expected,atol=0.15,rtol=0):
            problems['__scale__']='Mesh bounding box differs from CAD; check units and import.'
    (output/'zone_mapping.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if problems:
        # Manual fallback only after physical zone separation is reviewed. Never override a detected mixed zone or scale error.
        if any('Mixed physical' in v or 'outside expected' in v or 'Unexpected port' in v or k=='__scale__' for k,v in problems.items()):
            raise RuntimeError(f'Physical zone separation failed. See zone_mapping.json: {problems}')
        if manual is None: raise RuntimeError('Field-data mapping failed. Inspect zone_mapping.json and fluent_surfaces.json; provide a reviewed ZONE_MAP_FILE or fix importer.')
        manual_groups=json.loads(Path(manual).read_text(encoding='utf-8'))
        if set(manual_groups)!=set(GROUPS): raise ValueError('Manual mapping must have exactly the four group keys.')
        flat=[n for v in manual_groups.values() for n in v]
        if len(flat)!=len(set(flat)) or set(flat)!=set(actual): raise ValueError('Manual map must cover each actual exterior zone exactly once.')
        if any(n not in manual_groups[row['group']] for row in rows for n in [row['zone']]):
            raise ValueError('Manual map contradicts successfully classified geometry.')
        groups=manual_groups
        report['groups']=groups; report['manual_review_required']=True
        (output/'zone_mapping.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    if any(not v for v in groups.values()): raise RuntimeError('One or more physical groups missing; inspect face separation.')
    return groups

def apply_zone_types(solver,groups):
    bc=settings(solver).setup.boundary_conditions
    for group,names in groups.items():
        target=TYPES[group]
        current=getattr(bc,target.replace('-','_')).get_object_names()
        change=[name for name in names if name not in current]
        if change:
            if hasattr(bc,'set_zone_type'): bc.set_zone_type(zone_list=change,new_type=target)
            else:
                for name in change: solver.tui.define.boundary_conditions.zone_type(name,target)
        after=getattr(bc,target.replace('-','_')).get_object_names()
        if not set(names).issubset(after): raise RuntimeError(f'Zone type assignment failed or renamed zones: {group}')
