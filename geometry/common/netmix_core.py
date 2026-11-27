"""NETmix fluid-domain generator. All dimensions are in mm."""
from math import hypot, isfinite
import cadquery as cq

def build_netmix(n_rows, n_columns, dp, dd, width, pitch, height,
                 horizontal, port_diameter, port_length, port_side='top'):
    if any(not isinstance(n, int) or n < 3 or n % 2 == 0
           for n in (n_rows, n_columns)):
        raise ValueError('Use odd integer row and column counts >= 3.')
    if any(not isfinite(v) or v <= 0 for v in
           (dp, dd, width, pitch, height, port_diameter, port_length)):
        raise ValueError('All dimensions must be finite and positive.')
    if dp >= pitch or dd >= pitch or (dp + dd)/2 >= pitch/2**0.5:
        raise ValueError('Adjacent chambers overlap or touch.')
    if width >= min(dp, dd):
        raise ValueError('Channel width must be smaller than both diameters.')
    if horizontal and width >= pitch/2:
        raise ValueError('Horizontal and diagonal channels may overlap.')
    if port_diameter >= dp:
        raise ValueError('Port diameter must be smaller than parallel chamber diameter.')
    if port_side not in ('top', 'bottom'):
        raise ValueError("port_side must be 'top' or 'bottom'.")

    # Even/even = parallel chambers; odd/odd = diagonal chambers.
    centers = {(i,j): (i*pitch/2, j*pitch/2)
               for i in range(n_rows) for j in range(n_columns)
               if i % 2 == j % 2}
    solids = []
    for (i,j), (x,y) in centers.items():
        radius = (dp if i % 2 == 0 else dd)/2
        solids.append(cq.Solid.makeCylinder(radius, height, cq.Vector(x,y,0)))

    def channel(a,b):
        x1,y1 = centers[a]; x2,y2 = centers[b]
        dx,dy = x2-x1,y2-y1
        length = hypot(dx,dy)
        nx,ny = -dy/length*width/2, dx/length*width/2
        # Rectangle overlaps chambers up to their centres, ensuring fusion.
        pts = [(x1+nx,y1+ny),(x2+nx,y2+ny),
               (x2-nx,y2-ny),(x1-nx,y1-ny)]
        return cq.Workplane('XY').polyline(pts).close().extrude(height).val()

    diagonal_count = 0
    for i,j in centers:
        if i % 2 == 1:
            for di,dj in [(-1,-1),(-1,1),(1,-1),(1,1)]:
                solids.append(channel((i,j),(i+di,j+dj)))
                diagonal_count += 1

    horizontal_count = 0
    if horizontal:
        # Connect successive chambers along X in each transverse lane.
        for i,j in centers:
            if (i+2,j) in centers:
                solids.append(channel((i,j),(i+2,j)))
                horizontal_count += 1

    # Vertical cylindrical fluid extensions at the first and last stations.
    # Small internal overlap avoids relying on face-only Boolean contact.
    overlap = min(height/10, 0.1)
    z0 = height-overlap if port_side == 'top' else -port_length
    for i in (0,n_rows-1):
        for j in range(0,n_columns,2):
            x,y = centers[i,j]
            solids.append(cq.Solid.makeCylinder(port_diameter/2,
                          port_length+overlap,cq.Vector(x,y,z0)))

    print(f'Fusing {len(solids)} CAD primitives...', flush=True)
    result = solids[0].fuse(*solids[1:]).clean()
    if len(result.Solids()) != 1 or not result.isValid():
        raise RuntimeError('Expected one valid connected fluid solid.')
    box = result.BoundingBox()
    print(f'Parallel chambers: {sum(i%2==0 for i,j in centers)}')
    print(f'Diagonal chambers: {sum(i%2==1 for i,j in centers)}')
    print(f'Diagonal channels: {diagonal_count}; horizontal: {horizontal_count}')
    print(f'Inlets: {(n_columns+1)//2}; outlets: {(n_columns+1)//2}')
    print(f'Volume: {result.Volume():.3f} mm^3')
    print(f'Bounding box: {box.xlen:.3f} x {box.ylen:.3f} x {box.zlen:.3f} mm')
    return result

