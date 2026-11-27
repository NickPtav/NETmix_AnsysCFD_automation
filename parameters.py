"""Central configuration for NETmix CFD and optical simulation automation.

Geometry dimensions are in mm unless otherwise specified.
Machine-specific settings may be overridden in local_config.py.
"""

import importlib.util as _importlib_util
import os
from pathlib import Path


# ============================================================
# SOFTWARE CONFIGURATION
# ============================================================

FLUENT_VERSION = "26.1.0"
ANSYS_ROOT = os.environ.get(
    "AWP_ROOT261",
    r"C:\Program Files\ANSYS Inc\v261",
)
FLUENT_PATH = str(
    Path(ANSYS_ROOT) / "fluent" / "ntbin" / "win64" / "fluent.exe"
)
PROCESSORS = 4
SHOW_GUI = True
KEEP_GUI_ON_ERROR = True


# ============================================================
# NETMIX GEOMETRY
# ============================================================

N_ROWS = 9
N_COLUMNS = 3
D_PARALLEL = 6.5
D_DIAGONAL = D_PARALLEL
CHANNEL_WIDTH = 0.875
H = 12.0208  # Distance between parallel chambers
HEIGHT = 3.0
HORIZONTAL_CHANNELS = False

PORT_DIAMETER = 1.5
PORT_LENGTH = 3.0
PORT_SIDE = "top"
ILLUMINATION = "FSI"  # FSI or BSI
CATALYST_THICKNESS = 0.0173  # 17.3 micrometres; verify experimentally
TOL = 1e-6

# Geometry output and preview
CREATE_OPTICAL = False
EXPORT_INDIVIDUAL_BOUNDARIES = False
SHOW_VIEW = "none"  # none, boundaries, fluid, or optical


# ============================================================
# MESHING CONFIGURATION
# ============================================================

# Coarse smoke-test settings; revalidate for production simulations.
# Paper 2 used a nominal element size of 0.114 mm.
SURFACE_MAX_SIZE_MM = 0.5
VOLUME_MAX_SIZE_MM = 0.5
VOLUME_METHOD = "polyhedra"  # or multizone

CAD_SEPARATION_MODE = "None"  # or face, if supported by the importer
SURFACE_SEPARATION_REQUIRED = True
SURFACE_SEPARATION_ANGLE = 30.0
CAD_INPUT_OVERRIDE = None  # Optional .pmdb/.scdoc from the same STEP
PAUSE_AFTER_SURFACE = False

# MultiZone settings (verify imported region and labels)
MULTIZONE_REGION = None
MULTIZONE_SOURCE_LABELS = ["inlet", "outlet"]
MULTIZONE_INTERVALS = 10


# ============================================================
# FLUENT SOLVER CONFIGURATION
# ============================================================

INLET_VELOCITY = 1.5  # m/s, applied to every inlet
TCE_MOLE_FRACTION = 1.754e-5
WATER_MOLE_FRACTION = 0.09
INLET_TEMPERATURE_K = 300.0
OUTLET_GAUGE_PRESSURE_PA = 0.0
ITERATIONS = 500


# ============================================================
# PHYSICAL MODELS AND UDF
# ============================================================

RUN_SPECIES_TRANSPORT = True
RUN_REACTION = True
ACCEPT_LEGACY_PHYSICS = True

# Fixed UDF uses 995 W/m². Profile mode requires validation.
IRRADIANCE_MODE = "fixed"
PROFILE_UDF_SOURCE = None  # User-supplied UDF reading wall UDS
UDF_FUNCTION_NAME = "UDF_tce"
COMPILE_UDF = True  # Each solver run uses a fresh directory
UDF_LIBRARY = "libudf"

ACCEPT_PROFILE_MAPPING = False
PROFILE_FILE = None
PROFILE_NAME = None
PROFILE_FIELD = "irradiance"


# ============================================================
# BOUNDARY CONFIGURATION
# ============================================================

AUTO_CLASSIFY_BOUNDARIES = True
MERGE_BOUNDARY_ZONES = True
VALIDATE_BOUNDARY_AREAS = True

# Manual mapping must explicitly include every exterior zone.
ZONE_MAP_FILE = None
REQUIRE_ZONE_REVIEW = False


# ============================================================
# POST-PROCESSING AND VALIDATION
# ============================================================

RUN_POST_PROCESSING = False
MASS_BALANCE_TOL_PCT = 0.1
BOUNDARY_AREA_TOL_PCT = 5.0


# ============================================================
# OPTICAL GEOMETRY
# ============================================================

METAL_THICKNESS = 5.0
GLASS_THICKNESS = 3.0
PLATE_MARGIN_X = 4.75
PLATE_MARGIN_Y = 4.92

# The shared CATALYST_THICKNESS is defined in NETmix geometry.
CATALYST_OPTICAL_MODE = "surface"  # surface or volume
INCLUDE_GAS_BODY = False

# Optical tessellation (not yet validated for production)
OPTICAL_TOLERANCE = 0.01  # mm
OPTICAL_ANGULAR_TOLERANCE = 0.2  # rad


# ============================================================
# LED ARRAY GEOMETRY AND SOURCES
# ============================================================

LED_ROWS = 6
LED_COLUMNS = 3
LED_RADIUS = 1.45
LED_GLASS_GAP = 13.6
LED_RADIANT_POWER_W = 0.9  # Per LED
LED_INTENSITY_FILE = "CUN66A1B_160302.ies"
LED_SPECTRUM_FILE = "LED_900.spectrum"


# ============================================================
# OPTICAL MATERIALS AND INPUT FILES
# ============================================================

SPEOS_INPUT_DIR = Path(__file__).resolve().parent / "raytracing" / "input_files"
METAL_REFLECTANCE = 90.0  # Percent
TIO2_SURFACE_FILE = "Advanced_TiO2_10.scattering"
TIO2_VOLUME_FILE = None  # Set to the original material filename when available
GLASS_VOLUME_FILE = "Borosilicate_Glass.material"

# Known limitation: the original TiO2 SOP permits transmission and is
# incompatible with an opaque metal VOP in the fused FSI surface model.
# The optical workflow is under development; do not treat it as validated.


# ============================================================
# SPEOS SIMULATION AND SENSOR CONFIGURATION
# ============================================================

RUN_RAYTRACING = False
SPEOS_VERSION = "261"
SPEOS_PORT = 50098
SPEOS_BACKEND = "CPU"  # CPU or GPU (subject to license support)
SPEOS_THREADS = 4
SPEOS_N_RAYS = 15_000_000
SPEOS_TEST_RAYS = 100_000
SPEOS_SENSOR_NAME = "Catalyst_Irradiance"
SPEOS_SIMULATION_NAME = "NETmix_Direct"


# ============================================================
# OPTIONAL LOCAL CONFIGURATION (KEEP AT END)
# ============================================================

# Local settings override public defaults. Exclude local_config.py from Git.
if _importlib_util.find_spec("local_config") is not None:
    import local_config as _local_config

    for _name in dir(_local_config):
        if _name.isupper() and _name in globals():
            globals()[_name] = getattr(_local_config, _name)

    # Refresh derived defaults when only the parent setting is overridden.
    if hasattr(_local_config, "ANSYS_ROOT") and not hasattr(
        _local_config, "FLUENT_PATH"
    ):
        FLUENT_PATH = str(
            Path(ANSYS_ROOT) / "fluent" / "ntbin" / "win64" / "fluent.exe"
        )
    if hasattr(_local_config, "D_PARALLEL") and not hasattr(
        _local_config, "D_DIAGONAL"
    ):
        D_DIAGONAL = D_PARALLEL
