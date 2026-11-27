import os
from pathlib import Path
import ansys.fluent.core as pyfluent

# ANSYS installation
os.environ["AWP_ROOT261"] = (
    r"C:\Program Files\ANSYS Inc\ANSYS Student\v261"
)

fluent_path = Path(
    r"C:\Program Files\ANSYS Inc\ANSYS Student"
    r"\v261\fluent\ntbin\win64\fluent.exe"
)

print("PyFluent version:", pyfluent.__version__)
print("Executable exists:", fluent_path.is_file())

# Launch Fluent Meshing
session = pyfluent.launch_fluent(
    product_version="26.1.0",
    fluent_path=str(fluent_path),
    mode="meshing",
    dimension=3,
    precision="double",
    processor_count=4,
    ui_mode="gui",
    start_timeout=180
)

print("Fluent launched successfully!")

input("Press Enter to close Fluent...")

session.exit()