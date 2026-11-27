import cadquery as cq

def extrude(face, dz):
    return cq.Solid.extrudeLinear(face.outerWire(),face.innerWires(),cq.Vector(0,0,dz))

def at_z(f,z,tol):
    b=f.BoundingBox()
    return f.geomType()=='PLANE' and abs(b.zmin-z)<tol and abs(b.zmax-z)<tol

def wire_area(w):
    return cq.Face.makeFromWires(w).Area()

def offset_wire(w,t,expand):
    # Choose by actual area, independent of wire orientation.
    a=wire_area(w)
    for delta in (t,-t):
        try:
            out=w.offset2D(delta,kind='arc')
            if len(out)==1 and ((wire_area(out[0])>a) if expand else (wire_area(out[0])<a)):
                return out[0]
        except Exception:
            continue
    raise RuntimeError('Footprint offset failed or changed topology; inspect catalyst thickness.')

def make_catalyst(fluid,groups,height,port_side,illumination,t,tol=1e-6):
    if not 0<t<height/2:
        raise ValueError('Catalyst thickness must be positive and smaller than half the fluid depth.')
    if illumination.upper()=='BSI':
        parts=[extrude(f,t) for f in groups['catalytic_wall']]
    else:
        # Use the port-free planar face to reconstruct the exact core footprint.
        z=0 if port_side=='top' else height
        footprints=[f.translate(cq.Vector(0,0,-z)) for f in fluid.Faces() if at_z(f,z,tol)]
        if len(footprints)!=1:
            raise RuntimeError('Expected one planar core footprint.')
        f=footprints[0]
        outer=offset_wire(f.outerWire(),t,True)
        holes=[offset_wire(w,t,False) for w in f.innerWires()]
        expanded=cq.Solid.extrudeLinear(outer,holes,cq.Vector(0,0,height))
        core=extrude(f,height)
        side=expanded.cut(core).clean()
        # Extend the bottom coating to the offset footprint so it joins the side coating.
        # Remove the fluid and any bottom port extensions from the coating.
        base=cq.Solid.extrudeLinear(outer,holes,cq.Vector(0,0,-t)).cut(fluid).clean()
        parts=[side,base]
    if not parts:
        raise RuntimeError('No catalyst geometry produced.')
    result=parts[0].fuse(*parts[1:]).clean() if len(parts)>1 else parts[0]
    if not result.isValid() or result.Volume()<=0:
        raise RuntimeError('Invalid catalyst solid.')
    overlap=fluid.intersect(result).Volume()
    if overlap>max(1e-6,result.Volume()*1e-7):
        raise RuntimeError(f'Unexpected fluid/catalyst overlap: {overlap} mm³')
    print(f'Catalyst volume: {result.Volume():.6f} mm³; fluid overlap: {overlap:.3g} mm³')
    return result
