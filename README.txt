NETmix photocatalytic CAD generator

Open this folder in VS Code. Use the existing Python 3.12 environment with
CadQuery 2.8.0 and ocp-vscode 4.3.0. Edit parameters.py, then run main.py.
All dimensions are in mm. Open the OCP CAD Viewer before running.

Files: geometry.py builds the fluid solid; boundaries.py classifies its faces
and writes STEP subshape names/layers and CSV metadata; catalyst.py builds an
external coating with a coincident fluid interface; main.py exports and displays.

Outputs in output/: *_CFD.step (one fluid body with face metadata),
*_boundaries.csv (face metadata), *_inlet_faces.step, *_outlet_faces.step,
*_catalytic_wall_faces.step, *_non_catalytic_wall_faces.step (inspection sheets),
*_TiO2.step (coating), *_Optical.step (fluid and coating assembly).
Do not import separate face sheets alongside the CFD volume for meshing.
STEP metadata is not guaranteed to become Fluent Named Selections; verify import.
Optical assembly is partial: glass, steel, LED sources and optical materials/sensors
are not included. The coating extends outward to preserve the fluid domain.
Thickness 0.01 mm and port diameter 3 mm are illustrative, not verified.
Original geometry volume equivalence to SpaceClaim remains unverified.

Tests: BSI and FSI on 3x3 CH with top ports passed validity and zero-overlap
checks; BSI on imported 29-row CH model passed, catalyst area 4085.569667 mm2,
volume 40.855697 mm3. Full-scale FSI did not complete within test time.
FSI offset can fail for narrow features; errors are raised instead of silently
accepting topology changes. Bottom ports, full-size FSI and Ansys import remain
untested. Start with BSI; for FSI try N_ROWS=3 and N_COLUMNS=3 first.
