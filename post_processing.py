"""NETmix hydrodynamic post-processing for PyFluent 0.43.1.
Call after solving, with the current physical boundary mapping.
"""
import csv
import json
import math
from pathlib import Path

GROUPS = ('inlet', 'outlet', 'catalytic_wall', 'non_catalytic_wall')


def post_process(solver, groups, manifest, output, *, elapsed_s=None,
                 iterations=None, mass_tol_pct=0.1, area_tol_pct=2.0):
    from ansys.fluent.core.fields.reduction import functional as red

    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if set(groups) != set(GROUPS) or any(not groups[g] for g in GROUPS):
        raise ValueError('Expected four non-empty physical boundary groups')
    names = [n for g in GROUPS for n in groups[g]]
    if len(names) != len(set(names)):
        raise ValueError('Boundary groups overlap')
    fluid = solver.settings.setup.cell_zone_conditions.fluid.get_object_names()
    if not fluid:
        raise ValueError('No fluid cell zones found')
    cad_areas = manifest['group_areas_mm2']
    results, errors, checks = {}, {}, {}
    rows = []

    def record(key, fn):
        try:
            value = float(fn())
            if not math.isfinite(value):
                raise ValueError('Non-finite result')
            results[key] = value
            print(f'  {key}: {value:.8g}', flush=True)
            return value
        except Exception as exc:
            results[key] = None
            errors[key] = f'{type(exc).__name__}: {exc}'
            print(f'  FAILED {key}: {errors[key]}', flush=True)
            return None

    def available(*keys):
        return all(results.get(k) is not None for k in keys)

    print('\nNETmix post-processing', flush=True)
    for key, val in manifest.get('geometry', {}).items():
        if isinstance(val, (str, int, float, bool)):
            results[f'geometry_{key}'] = val

    for g in GROUPS:
        loc = list(groups[g])
        results[f'{g}_zone_count'] = len(loc)
        area = record(f'{g}_area_mm2', lambda: red.area(loc, ctxt=solver)*1e6)
        ref = record(f'{g}_cad_area_mm2', lambda: cad_areas[g])
        err = record(f'{g}_area_error_pct', lambda: abs(area-ref)/ref*100) if area is not None and ref is not None and ref > 0 else None
        checks[f'{g}_area'] = None if err is None else err <= area_tol_pct
        rows.append({'group': g, 'zone_count': len(loc), 'mesh_area_mm2': area,
                     'cad_area_mm2': ref, 'area_error_pct': err,
                     'within_tolerance': checks[f'{g}_area']})

    for g in ('inlet', 'outlet'):
        loc = list(groups[g])
        record(f'{g}_mass_flow_kg_s', lambda: red.mass_flow(loc, ctxt=solver))
        record(f'{g}_absolute_pressure_Pa', lambda: red.area_average('AbsolutePressure', loc, ctxt=solver))
        record(f'{g}_velocity_m_s', lambda: red.area_average('VelocityMagnitude', loc, ctxt=solver))

    if available('inlet_mass_flow_kg_s', 'outlet_mass_flow_kg_s'):
        mi, mo = results['inlet_mass_flow_kg_s'], results['outlet_mass_flow_kg_s']
        if abs(mi) > 0:
            err = record('mass_balance_error_pct', lambda: abs(mi+mo)/abs(mi)*100)
            checks['mass_balance'] = err <= mass_tol_pct and mi*mo < 0
        else:
            errors['mass_balance_error_pct'] = 'Zero inlet mass flow'
            checks['mass_balance'] = False
    else:
        checks['mass_balance'] = None
    if available('inlet_absolute_pressure_Pa', 'outlet_absolute_pressure_Pa'):
        record('pressure_drop_Pa', lambda: results['inlet_absolute_pressure_Pa']-results['outlet_absolute_pressure_Pa'])
    record('fluid_volume_mm3', lambda: red.volume(fluid, ctxt=solver)*1e9)
    record('cell_count', lambda: red.count(fluid, ctxt=solver))
    record('volume_average_velocity_m_s', lambda: red.volume_average('VelocityMagnitude', fluid, ctxt=solver))
    record('maximum_velocity_m_s', lambda: red.maximum('VelocityMagnitude', fluid, ctxt=solver))
    if available('catalytic_wall_area_mm2','fluid_volume_mm3') and results['fluid_volume_mm3'] > 0:
        record('specific_catalytic_area_m_inv', lambda: 1000*results['catalytic_wall_area_mm2']/results['fluid_volume_mm3'])
    results['elapsed_s'] = elapsed_s
    results['iterations'] = iterations
    results['mass_tolerance_pct'] = mass_tol_pct
    results['area_tolerance_pct'] = area_tol_pct
    results['all_checks_passed'] = not errors and all(v is True for v in checks.values())
    with (output/'hydrodynamic_results.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(results))
        writer.writeheader()
        writer.writerow(results)
    with (output/'boundary_area_validation.csv').open('w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    report = {'results': results, 'checks': checks, 'errors': errors, 'groups': groups,
              'fluid_zones': list(fluid)}
    (output/'post_processing.json').write_text(json.dumps(report, indent=2, default=str, allow_nan=False), encoding='utf-8')
    print(f'\nPost-processing saved to {output}', flush=True)
    print(f"All checks passed: {results['all_checks_passed']}", flush=True)
    return report
