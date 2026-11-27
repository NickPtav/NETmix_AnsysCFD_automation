"""Original validation-script material values and TUI reaction mechanism.
Review before scientific use.
"""

def configure_materials(solver, root):

    # ============================================================
    # TCE MATERIAL
    # ============================================================

    solver.tui.define.materials.copy(
        "fluid", "air", "tce"
    )

    root.setup.materials.fluid['tce'] = {
        "density": {
            "option": "constant",
            "value": 1460.
        },
        "specific_heat": {
            "option": "constant",
            "value": 120.1
        },
        "thermal_conductivity": {
            "option": "constant",
            "value": 0.1159
        },
        "viscosity": {
            "option": "constant",
            "value": 0.00053
        },
        "molecular_weight": {
            "option": "constant",
            "value": 131.38
        },
        "formation_entropy": {
            "option": "constant",
            "value": 2.284e-05
        }
    }

    # ============================================================
    # WATER VAPOR
    # ============================================================

    solver.tui.define.materials.copy(
        "fluid", "water-vapor"
    )

    # ============================================================
    # MIXTURE AND REACTION CONFIGURATION
    # ============================================================

    parameters = [

        "mixture-template", "mixture-template",

        # Mixture species
        "yes", "3",
        "tce", "water-vapor", "air",

        # Reaction configuration
        "0", "0", "yes", "1",
        "reaction-1",
        "yes", "no", "no",

        # Reactants
        "3",
        "tce", "1", "1",
        "water-vapor", "1", "1",
        "air", "1", "1",

        # Products and kinetic parameters
        "0",
        "1000000000000000",
        "100000000",
        "0",

        # Modified TUI sequence for testing
        "no", "no", "no",

        # Density
        "yes", "volume-weighted-mixing-law",

        # Specific heat
        "yes", "mixing-law",

        # Thermal conductivity
        "yes", "mass-weighted-mixing-law",

        # Viscosity
        "yes", "mass-weighted-mixing-law",

        # Mass diffusivity
        "yes", "kinetic-theory",

        "no"
    ]

    # ============================================================
    # APPLY MIXTURE CONFIGURATION
    # ============================================================

    solver.tui.define.materials.change_create(
        *parameters
    )