"""Generate an independent optical CAD assembly from a saved CFD case.
Run from repository root: python -m geometry.optical.optical_setup --case NAME --show
All dimensions are mm. No Speos license needed for this stage.
"""
import argparse
import hashlib
import json
from itertools import combinations
from pathlib import Path

import cadquery as cq
from geometry.cfd.boundaries import classify
from geometry.optical.catalyst import make_catalyst
from main import config, case_name, locate_case, OUTPUT, new_directory


def box(x0, y0, z0, x1, y1, z1):
    return cq.Solid.makeBox(x1-x0, y1-y0, z1-z0, cq.Vector(x0,y0,z0))


def export(shape, path):
    cq.exporters.export(shape, str(path))


def generate_optical(p, case, show=False):
    case = Path(case).resolve()
    step = case / 'CFD.step'
    manifest = json.loads((case / 'geometry.json').read_text(encoding='utf-8'))
    # Saved CFD geometry, not the current geometry defaults, is authoritative.
    for key, value in manifest['geometry'].items():
        setattr(p, key, value)
    if p.PORT_SIDE != 'top':
        raise ValueError('First optical implementation supports top ports only.')
    h, t, tol = p.HEIGHT, p.CATALYST_THICKNESS, p.TOL
    metal_t = getattr(p, 'METAL_THICKNESS', 5.0)
    glass_t = getattr(p, 'GLASS_THICKNESS', 4.0)
    mx = getattr(p, 'PLATE_MARGIN_X', 4.75)
    my = getattr(p, 'PLATE_MARGIN_Y', 4.92)
    nr = getattr(p, 'LED_ROWS', 6)
    nc = getattr(p, 'LED_COLUMNS', 3)
    radius = getattr(p, 'LED_RADIUS', 1.45)
    gap = getattr(p, 'LED_GLASS_GAP', 13.6)
    if min(metal_t, glass_t, mx, my, radius, gap) <= 0 or metal_t <= h+t:
        raise ValueError('Invalid optical dimensions or insufficient metal thickness.')
    if not isinstance(nr,int) or not isinstance(nc,int) or min(nr,nc)<1:
        raise ValueError('LED counts must be positive integers.')
    solids = cq.importers.importStep(str(step)).solids().vals()
    if len(solids) != 1 or not solids[0].isValid():
        raise RuntimeError('Expected one valid CFD solid.')
    fluid = solids[0]
    if abs(fluid.Volume()-manifest['volume_mm3']) > max(1e-5,fluid.Volume()*1e-6):
        raise RuntimeError('CFD STEP volume differs from saved manifest.')
    groups = classify(fluid,h,p.PORT_LENGTH,p.PORT_SIDE,p.ILLUMINATION,tol)
    for name,faces in groups.items():
        area=sum(f.Area() for f in faces)
        if abs(area-manifest['group_areas_mm2'][name])>max(1e-5,area*1e-6):
            raise RuntimeError(f'Boundary area mismatch: {name}')
    catalyst = make_catalyst(fluid,groups,h,p.PORT_SIDE,p.ILLUMINATION,t,tol)
    x0,y0=-mx,-my
    x1=(p.N_ROWS-1)*p.H/2+mx
    y1=(p.N_COLUMNS-1)*p.H/2+my
    bb=catalyst.BoundingBox()
    if bb.xmin<x0-tol or bb.xmax>x1+tol or bb.ymin<y0-tol or bb.ymax>y1+tol:
        raise ValueError('Increase plate margins to contain catalyst.')
    metal=box(x0,y0,h-metal_t,x1,y1,h).cut(fluid,catalyst).clean()
    # BSI coating is above the CFD fluid; glass rests above that coating.
    # The full glass slab is cut by catalyst to maintain a seal outside the coating.
    glass_top=h+glass_t
    glass_blank=box(x0,y0,h,x1,y1,glass_top)
    ports=[]
    for f in groups['inlet']+groups['outlet']:
        c=f.Center()
        ports.append(cq.Solid.makeCylinder(p.PORT_DIAMETER/2,glass_t+0.1,cq.Vector(c.x,c.y,h-0.1)))
    glass=glass_blank.cut(catalyst,*ports).clean()
    # Adjust optical gas extensions to physical glass top only; CFD STEP unchanged.
    core=fluid.intersect(box(x0,y0,0,x1,y1,h))
    gas=core.fuse(*ports).clean()
    bodies={'metal_plate':metal,'TiO2':catalyst,'glass':glass,'gas':gas}
    for name,shape in bodies.items():
        if not shape.isValid() or shape.Volume()<=0 or len(shape.Solids())!=1:
            raise RuntimeError(f'Invalid or disconnected optical body: {name}')
    overlaps={}
    for (a,s),(b,q) in combinations(bodies.items(),2):
        v=s.intersect(q).Volume()
        overlaps[f'{a}/{b}']=v
        if v>max(1e-6,min(s.Volume(),q.Volume())*1e-8):
            raise RuntimeError(f'Unintended overlap {a}/{b}: {v} mm3')
    dx,dy=(x1-x0)/(nr+1),(y1-y0)/(nc+1)
    if min(dx,dy)<2*radius:
        raise ValueError('LED discs overlap or are too close to plate edge.')
    leds={}
    led_info=[]
    for i in range(nr):
        for j in range(nc):
            name=f'LED_{i*nc+j+1:03d}'
            center=(x0+(i+1)*dx,y0+(j+1)*dy,glass_top+gap)
            wire=cq.Wire.makeCircle(radius,cq.Vector(*center),cq.Vector(0,0,-1))
            leds[name]=cq.Face.makeFromWires(wire)
            led_info.append({'name':name,'center_mm':center,'emission_direction':[0,0,-1],'radius_mm':radius})
    out=new_directory(case,'optical')
    assy=cq.Assembly(name='NETmix_optical')
    colors={'metal_plate':'gray','TiO2':'gold','glass':'lightblue','gas':'cyan'}
    for name,shape in bodies.items():
        assy.add(shape,name=name,color=cq.Color(colors[name]))
        export(shape,out/f'{name}.step')
    for name,face in leds.items():
        assy.add(face,name=name,color=cq.Color('purple'))
        export(face,out/f'{name}.step')
    assy.export(str(out/'Optical.step'),exportType='STEP')
    # Reference faces only; never add these as duplicate geometry to the optical scene.
    export(cq.Compound.makeCompound(groups['catalytic_wall']),out/'catalytic_interface_reference.step')
    data={'units':'mm','cfd_step_sha256':hashlib.sha256(step.read_bytes()).hexdigest(),
          'geometry':manifest['geometry'],'metal_thickness_mm':metal_t,'glass_thickness_mm':glass_t,
          'plate_margins_mm':[mx,my],'led_glass_gap_mm':gap,'leds':led_info,
          'body_volumes_mm3':{k:s.Volume() for k,s in bodies.items()},'overlap_mm3':overlaps,
          'catalytic_reference_area_mm2':sum(f.Area() for f in groups['catalytic_wall']),
          'notes':'Centered LED grid; gas ports adjusted to glass top. Reference faces are not optical bodies.'}
    (out/'optical_geometry.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
    print(f'Optical geometry saved: {out}')
    if show:
        from ocp_vscode import show as display
        display(assy)
    return out


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',help='Saved CFD case name or path')
    parser.add_argument('--show',action='store_true')
    args=parser.parse_args()
    p=config(False)
    case=locate_case(args.case) if args.case else OUTPUT/case_name(p)
    generate_optical(p,case,args.show)


if __name__=='__main__':
    main()
