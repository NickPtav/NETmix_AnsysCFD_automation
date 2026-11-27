"""
NETmix optical automation.

Basic connectivity test for Ansys Speos 2026 R1.
"""

from ansys.speos.core.launcher import (
    launch_local_speos_rpc_server
)


def main():

    speos = None

    try:

        print("Launching Ansys Speos RPC server...")

        speos = launch_local_speos_rpc_server(
            version="261"
        )

        print("Speos connection established.")
        print(speos)

    except Exception as error:

        print("Speos connection failed.")
        print(error)
        raise

    finally:

        if speos is not None:

            speos.close()
            print("Speos session closed.")


if __name__ == "__main__":
    main()