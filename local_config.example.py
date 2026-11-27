"""Example local configuration.

Copy this file to local_config.py and modify
the settings according to your computer.
"""

# Ansys installation directory

ANSYS_ROOT = r"C:\path\to\your\ANSYS\installation"

FLUENT_PATH = (
    ANSYS_ROOT + r"\fluent\ntbin\win64\fluent.exe"
)

FLUENT_VERSION = "26.1.0"

# Computational settings

PROCESSORS = 4

SHOW_GUI = True

# Optional solver settings

PAUSE_AFTER_SURFACE = False

REQUIRE_ZONE_REVIEW = False

KEEP_GUI_ON_ERROR = True