"""
NETmix radiometric sensors.
"""

from ansys.speos.core.sensor import Sensor3DIrradiance


def configure_sensor(
    project,
    p,
    catalytic_faces
):

    if not catalytic_faces:

        raise ValueError(
            "No catalytic faces were identified."
        )

    sensor = project.create_sensor(
        name=p.SPEOS_SENSOR_NAME,
        feature_type=Sensor3DIrradiance
    )

    # Select only the relevant catalyst surfaces

    sensor.geometries = catalytic_faces

    # Radiometric measurements

    sensor.set_type_radiometric()

    sensor.commit()

    print(
        f"3D irradiance sensor configured on "
        f"{len(catalytic_faces)} faces."
    )

    return sensor