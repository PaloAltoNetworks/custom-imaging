
from lib.script_logger import Logger
from lib.utils import CustomAmi


CONFIG_FILE = "config.yaml"


def main():

    # Custom AMI library Initialization
    lib = CustomAmi(logger, 'aws', CONFIG_FILE)

    # Create a base Instance(EC2)
    lib.cloud_client.create_instance()

    try:
        # Connect to FW Instance
        lib.connect_to_vmseries()

        # License the FW
        lib.license_firewall()

        # Verify System
        lib.verify_system()

        # Upgrade Content
        lib.upgrade_content()

        # Upgrade Anti-virus
        lib.upgrade_antivirus()

        # Upgrade Global-Protect Clientless VPN
        lib.upgrade_gp_cvpn()

        # Upgrade Wildfire
        lib.upgrade_wildfire()

        # Upgrade VM Series Plugin
        lib.upgrade_plugin()

        # Upgrade PanOS
        lib.upgrade_panos()

        # Verify Upgrades
        lib.verify_upgrades()

        # Perform Private Data Reset
        lib.private_data_reset()

        # Verify Upgrades after Private Data Reset
        lib.verify_upgrades()

        # Close connection to the Firewall
        lib.handler.close()

        # Create Custom AMI
        lib.create_custom_ami()

        # Cleanup
        logger.info('*** Terminating Base Instance ***')
        lib.cloud_client.terminate_instance()
        logger.info('*** Termination Complete ***')

    except Exception as e:
        # Failed
        logger.error(f'*** Failed to Create Custom AMI ***')
        logger.error(f'TRACEBACK: {str(e)}')
        # Terminating created Instance(EC2)
        logger.info('*** Terminating Base Instance ***')
        lib.cloud_client.terminate_instance()
        logger.info('*** Termination Complete ***')


if __name__ == '__main__':
    # Setup Logger
    logger = Logger(console=True)
    # Create Custom AMI
    main()
