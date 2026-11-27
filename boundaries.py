import cadquery as cq
import csv

COLORS = {'inlet':'blue','outlet':'orange','catalytic_wall':'green','non_catalytic_wall':'gray'}

def classify(fluid, height, port_length, port_side, illumination, tol=1e-6):
    illumination = illumination.upper()
    if illumination not in ('BSI','FSI'):
        raise ValueError('Choose BSI or FSI.')
    groups = {name: [] for name in COLORS}
    bb = fluid.BoundingBox()
    xmid = (bb.xmin + bb.xmax)/2
    zend = height+port_length if port_side=='top' else -port_length
    def planar_at(face,z):
        b=face.BoundingBox()
        return face.geomType()=='PLANE' and abs(b.zmin-z)<tol and abs(b.zmax-z)<tol
    for f in fluid.Faces():
        b=f.BoundingBox()
        if planar_at(f,zend):
            key='inlet' if f.Center().x<xmid else 'outlet'
        else:
            top=planar_at(f,height)
            bottom=planar_at(f,0)
            side=abs(b.zmin)<tol and abs(b.zmax-height)<tol
            catalytic=top if illumination=='BSI' else bottom or side
            key='catalytic_wall' if catalytic else 'non_catalytic_wall'
        groups[key].append(f)
    if any(not fs for fs in groups.values()):
        raise RuntimeError('Missing boundary group; inspect geometry.')
    for name,fs in groups.items():
        print(f'{name}: {len(fs)} faces, {sum(f.Area() for f in fs):.6f} mm²')
    return groups

def export_named(fluid, groups, path, csv_path):
    # Metadata on original faces, not duplicate sheet bodies.
    assy=cq.Assembly(fluid, name='fluid_domain')
    with open(csv_path,'w',newline='',encoding='utf-8') as stream:
        w=csv.writer(stream)
        w.writerow(['group','face_name','area_mm2','cx_mm','cy_mm','cz_mm','xmin_mm','xmax_mm','ymin_mm','ymax_mm','zmin_mm','zmax_mm','surface_type'])
        for name,fs in groups.items():
            for i,f in enumerate(fs,1):
                tag=f'{name}_{i:04d}'
                assy.addSubshape(f,name=tag,layer=name,color=cq.Color(COLORS[name]))
                c=f.Center(); b=f.BoundingBox()
                w.writerow([name,tag,f.Area(),c.x,c.y,c.z,b.xmin,b.xmax,b.ymin,b.ymax,b.zmin,b.zmax,f.geomType()])
    assy.export(str(path),exportType='STEP')
