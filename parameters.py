import os
from pathlib import Path

# ============================================================
# SOFTWARE CONFIGURATION
# ============================================================

FLUENT_VERSION = "26.1.0"

ANSYS_ROOT = os.environ.get(
    "AWP_ROOT261",
    r"C:\Program Files\ANSYS Inc\v261"
)

FLUENT_PATH = str(
    Path(ANSYS_ROOT)
    / "fluent"
    / "ntbin"
    / "win64"
    / "fluent.exe"
)

PROCESSORS = 4
SHOW_GUI = True

# All lengths in mm. Geometry conventions inherited from the previous generator.
N_ROWS = 9
N_COLUMNS = 3
D_PARALLEL = 6.5
D_DIAGONAL = D_PARALLEL
CHANNEL_WIDTH = 0.875
H = 12.0208          # DIstance between paralel chambers
HEIGHT = 3.0         # Reactor Height
HORIZONTAL_CHANNELS = False
PORT_DIAMETER = 1.5  # Inlet diameter
PORT_LENGTH = 3.0    # Inlet Height   
PORT_SIDE = 'top'
ILLUMINATION = 'FSI'  # BSI or FSI
CATALYST_THICKNESS = 0.01  # illustrative 10 micrometres; verify experimentally
TOL = 1e-6

# Geometry output; optical construction is independent of meshing.
CREATE_OPTICAL = False
EXPORT_INDIVIDUAL_BOUNDARIES = False
SHOW_VIEW = 'none'  # choose boundaries/fluid/optical to preview
PROCESSORS = 4
SHOW_GUI = True
SURFACE_MAX_SIZE_MM = 0.5  # original meshing_setup; smoke test only
# Paper 2 selected 0.114 mm nominal element size. Revalidate on new CAD.
VOLUME_METHOD = 'polyhedra'  # or 'multizone' (requires verified imported labels)
VOLUME_MAX_SIZE_MM = 0.5
CAD_SEPARATION_MODE = 'None'  # or 'face' if supported by installed importer
SURFACE_SEPARATION_REQUIRED = True
SURFACE_SEPARATION_ANGLE = 30.0

PAUSE_AFTER_SURFACE = True
CAD_INPUT_OVERRIDE = None  # optional .pmdb/.scdoc converted from the SAME STEP
MULTIZONE_REGION = None  # exact region name from Update Regions, if using MultiZone
MULTIZONE_SOURCE_LABELS = ['inlet', 'outlet']  # exact imported labels; verify
MULTIZONE_INTERVALS = 10
PAUSE_AFTER_SURFACE = False  # This pauses the meshing before going to volumetric, and asks if you want to proceed
KEEP_GUI_ON_ERROR = True

# ============================================================
# SOLVER CONFIGURATION (fluent)
# ============================================================
INLET_VELOCITY = 1.5  # m/s, applied to every inlet
TCE_MOLE_FRACTION = 1.754e-5
WATER_MOLE_FRACTION = 0.09
INLET_TEMPERATURE_K = 300.0
OUTLET_GAUGE_PRESSURE_PA = 0.0
ITERATIONS = 500

# ============================================================
# PHYSICAL MODELS
# ============================================================

RUN_SPECIES_TRANSPORT = True
RUN_REACTION = True
ACCEPT_LEGACY_PHYSICS = True
# Fixed UDF uses 995 W/m2. Profile mode requires a separately validated UDF.
IRRADIANCE_MODE = 'fixed'
PROFILE_UDF_SOURCE = None  # user-supplied source that reads wall UDS, not fixed UDF
UDF_FUNCTION_NAME = 'UDF_tce'
COMPILE_UDF = True  # required: each solver run uses a fresh directory
UDF_LIBRARY = 'libudf'

ACCEPT_PROFILE_MAPPING = False  # validate spatial mapping and UDF before enabling
PROFILE_FILE = None
PROFILE_NAME = None
PROFILE_FIELD = 'irradiance'

# Optional manual zone mapping file. Must explicitly include every exterior zone.
ZONE_MAP_FILE = None
    # Require a separate explicit review before solver setup / iterations.
REQUIRE_ZONE_REVIEW = False  # If "True" it will pause fluent for a check. 
SHOW_GUI = True
PROCESSORS = 4
# ============================================================
# BOUNDARY CONFIGURATION
# ============================================================

AUTO_CLASSIFY_BOUNDARIES = True

MERGE_BOUNDARY_ZONES = True

VALIDATE_BOUNDARY_AREAS = True

# ============================================================
# POST-PROCESSING CONFIGURATION
# ============================================================

RUN_POST_PROCESSING = True

# Maximum acceptable mass conservation error (%)
MASS_BALANCE_TOL_PCT = 0.1

# Maximum acceptable CAD-to-mesh surface area deviation (%)
BOUNDARY_AREA_TOL_PCT = 5.0

# ============================================================
# OPTIONAL LOCAL CONFIGURATION
# ============================================================
# Local settings override the public defaults.
# local_config.py is excluded from GitHub.

import importlib.util as _importlib_util

if _importlib_util.find_spec("local_config") is not None:

    import local_config as _local_config

    for _name in dir(_local_config):

        if _name.isupper() and _name in globals():

            globals()[_name] = getattr(
                _local_config,
                _name
            )