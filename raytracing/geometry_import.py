"""Transfer saved optical CAD to Speos; all lengths in mm."""
import json
from pathlib import Path
import cadquery as cq
import numpy as np


def load_shape(path):
    return cq.importers.importStep(str(path)).val()


def tessellate_face(cad_face, tolerance=0.01, angular_tolerance=0.2):
    vertices, triangles = cad_face.tessellate(tolerance, angular_tolerance)
    coordinates, facets, normals = [], [], []
    for triangle in triangles:
        points = np.array([vertices[i].toTuple() for i in triangle])
        normal = np.cross(points[1]-points[0], points[2]-points[0])
        norm = np.linalg.norm(normal)
        if norm < 1e-14:
            continue
        normal /= norm
        start = len(coordinates)//3
        coordinates.extend(points.ravel().tolist())
        normals.extend(np.tile(normal, 3).tolist())
        facets.extend([start, start+1, start+2])
    if not facets:
        raise RuntimeError('Empty face tessellation')
    return coordinates, facets, normals


def match_faces(shape, reference, expected_area):
    """Require complete face coverage, not just matching centroids."""
    matches = []
    for i, face in enumerate(shape.Faces()):
        area = face.Area()
        overlap = face.intersect(reference).Area()
        eps = max(1e-6, area*1e-5)
        if overlap <= eps:
            continue
        if abs(overlap-area) > eps:
            raise RuntimeError(f'Face {i+1} partially coated: {overlap}/{area} mm²; needs splitting')
        matches.append(i)
    actual = sum(shape.Faces()[i].Area() for i in matches)
    if not matches or abs(actual-expected_area)>max(1e-4, expected_area*1e-5):
        raise RuntimeError(f'Catalytic area mismatch: {actual} vs {expected_area} mm²')
    print(f'Catalytic interface: {len(matches)} faces, {actual:.6f} mm²')
    return set(matches)


def import_body(root, shape, name, tolerance, angular_tolerance, coated=()):
    body = root.create_body(name=name).commit()
    faces, catalytic = [], []
    count = 0
    for i, cad_face in enumerate(shape.Faces()):
        v, f, n = tessellate_face(cad_face, tolerance, angular_tolerance)
        face = body.create_face(name=f'{name}_Face_{i+1:04d}')
        face.vertices, face.facets, face.normals = v, f, n
        face.commit()
        faces.append(face)
        if i in coated:
            catalytic.append(face)
        count += len(f)//3
    print(f'{name}: {len(faces)} faces, {count} triangles')
    return dict(body=body, faces=faces, catalytic_faces=catalytic,
                n_faces=len(faces), n_triangles=count)


def import_optical_geometry(project, optical_dir, tolerance=0.01,
                            angular_tolerance=0.2, *, catalyst_mode='surface',
                            include_gas=False):
    d = Path(optical_dir)
    meta = json.loads((d/'optical_geometry.json').read_text(encoding='utf-8'))
    illumination = meta['geometry']['ILLUMINATION'].upper()
    mode = catalyst_mode.lower()
    if mode not in ('surface','volume') or illumination not in ('FSI','BSI'):
        raise ValueError('Invalid catalyst mode or illumination')
    shapes = {k: load_shape(d/f) for k,f in [('metal','metal_plate.step'),
               ('catalyst','TiO2.step'),('glass','glass.step')]}
    target = 'catalyst'
    if mode == 'surface':
        target = 'metal' if illumination == 'FSI' else 'glass'
        a,b = shapes[target], shapes.pop('catalyst')
        fused = a.fuse(b).clean()
        if not fused.isValid() or len(fused.Solids()) != 1:
            raise RuntimeError('Coating/support fusion did not form one valid solid')
        if abs(fused.Volume()-a.Volume()-b.Volume()) > max(1e-5, fused.Volume()*1e-7):
            raise RuntimeError('Unexpected volume after fusion')
        shapes[target] = fused
    if include_gas:
        shapes['gas'] = load_shape(d/'gas.step')
    reference = load_shape(d/'catalytic_interface_reference.step')
    # STEP import can return several top-level shapes; retain all reference faces.
    reference = cq.Compound.makeCompound(cq.importers.importStep(str(d/'catalytic_interface_reference.step')).faces().vals())
    coated = match_faces(shapes[target], reference, meta['catalytic_reference_area_mm2'])
    root = project.create_root_part().commit()
    geometry = {}
    for name, shape in shapes.items():
        geometry[name] = import_body(root, shape, name, tolerance, angular_tolerance,
                                     coated if name == target else ())
    geometry['catalytic_faces'] = geometry[target]['catalytic_faces']
    geometry['leds'] = []
    for info in meta['leds']:
        name = info['name']
        shape = load_shape(d/f'{name}.step')
        if len(shape.Faces()) != 1:
            raise RuntimeError(f'{name}: expected one emitting face')
        item = import_body(root, shape, name, tolerance, angular_tolerance)
        normal = shape.Faces()[0].normalAt().toTuple()
        direction = info['emission_direction']
        item.update(face=item['faces'][0], reverse_normal=bool(np.dot(normal,direction)<0),
                    center_mm=info['center_mm'], emission_direction=direction)
        geometry['leds'].append(item)
    all_bodies = [geometry[k] for k in shapes]+geometry['leds']
    print(f"Bodies: {len(all_bodies)}; Faces: {sum(x['n_faces'] for x in all_bodies)}; Triangles: {sum(x['n_triangles'] for x in all_bodies)}; LEDs: {len(geometry['leds'])}")
    return geometry
