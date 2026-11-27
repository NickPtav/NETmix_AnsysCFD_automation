"""Generate one CFD STEP and optional optical STEP, plus boundary manifest."""
import json
from pathlib import Path
import cadquery as cq
from geometry.common.netmix_core import build_netmix

from geometry.cfd.boundaries import (
    classify,
    export_named,
    COLORS
)

from geometry.optical.catalyst import make_catalyst

GEOMETRY_KEYS = ('N_ROWS','N_COLUMNS','D_PARALLEL','D_DIAGONAL','CHANNEL_WIDTH','H','HEIGHT','HORIZONTAL_CHANNELS','PORT_DIAMETER','PORT_LENGTH','PORT_SIDE','ILLUMINATION','CATALYST_THICKNESS','TOL')

def geometry_config(p):
    return {k:getattr(p,k) for k in GEOMETRY_KEYS}

def generate(p, out):
    out = Path(out).resolve(); out.mkdir(parents=True, exist_ok=True)
    if p.SHOW_VIEW == 'optical' and not p.CREATE_OPTICAL:
        raise ValueError('Enable CREATE_OPTICAL to use the optical viewer.')
    fluid = build_netmix(p.N_ROWS,p.N_COLUMNS,p.D_PARALLEL,p.D_DIAGONAL,
        p.CHANNEL_WIDTH,p.H,p.HEIGHT,p.HORIZONTAL_CHANNELS,p.PORT_DIAMETER,p.PORT_LENGTH,p.PORT_SIDE)
    groups = classify(fluid,p.HEIGHT,p.PORT_LENGTH,p.PORT_SIDE,p.ILLUMINATION,p.TOL)
    for name in ('inlet','outlet'):
        if len(groups[name]) != (p.N_COLUMNS+1)//2:
            raise RuntimeError(f'Unexpected {name} CAD face count')
    step = out/'CFD.step'
    export_named(fluid,groups,step,out/'boundaries.csv')
    bb=fluid.BoundingBox()
    manifest={'geometry':geometry_config(p), 'units':'mm', 'volume_mm3':fluid.Volume(),
              'bounds_mm':[bb.xmin,bb.xmax,bb.ymin,bb.ymax,bb.zmin,bb.zmax],
              'group_areas_mm2':{k:sum(f.Area() for f in fs) for k,fs in groups.items()},
              'group_face_counts':{k:len(v) for k,v in groups.items()}}
    (out/'geometry.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
    if p.EXPORT_INDIVIDUAL_BOUNDARIES:
        for name,fs in groups.items():
            cq.exporters.export(cq.Compound.makeCompound(fs),str(out/f'{name}_faces.step'))
    catalyst=None
    if p.CREATE_OPTICAL:
        catalyst=make_catalyst(fluid,groups,p.HEIGHT,p.PORT_SIDE,p.ILLUMINATION,p.CATALYST_THICKNESS,p.TOL)
        assy=cq.Assembly(name='NETmix_optical_partial')
        assy.add(fluid,name='fluid_domain',color=cq.Color('lightblue'))
        assy.add(catalyst,name='TiO2',color=cq.Color('gold'))
        assy.export(str(out/'Optical.step'),exportType='STEP')
    if p.SHOW_VIEW != 'none':
        from ocp_vscode import show
        if p.SHOW_VIEW=='boundaries':
            show(*(cq.Compound.makeCompound(fs) for fs in groups.values()),names=list(groups),colors=list(COLORS.values()))
        elif p.SHOW_VIEW=='fluid': show(fluid,names=['Fluid domain'])
        elif p.SHOW_VIEW=='optical': show(fluid,catalyst,names=['Fluid domain','TiO2'])
        else: raise ValueError('Unknown SHOW_VIEW')
    return step
