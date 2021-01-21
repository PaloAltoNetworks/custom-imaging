# Copyright 2019 Palo Alto Networks
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import yaml
import time

from cloudclient.cloud_client import CloudProvider
from lib.pandevice import PanosDevice

FIRST_WAIT = 660
INTERVAL = 120


class CustomImage(object):
    def __init__(self, logger, filename):
        self.logger = logger
        self.config = {}
        # Fetch Inputs From Config File
        self.config = self.fetch_config_yaml(filename)
        # Connect to the public Cloud
        self.cloud_client = CloudProvider(self.logger, self.config["cloud_provider"], self.config)
        self.handler =None

    def fetch_config_yaml(self, filename):
        self.logger.info(f'Reading configuration file {filename}.')
        with open(filename) as file:
            config = yaml.load(file, Loader=yaml.FullLoader)
        if not config:
            self.logger.error(f'Unable to read configuration file {filename}.')
        output = {}
        try:
            if config["cloud-provider"].lower() == "aws":
                output['ami_id'] = config['ami-id']
                output['mgmt_subnet_id'] = config['mgmt-subnet-id']
                output['sg_id'] = config['sg-id']
                output['key_pair_name'] = config['key-pair-name']
                output['instance_type'] = config['instance-type']
                output['kms_key_id'] = config['kms-key-id']
                output['ami_description'] = config['ami-description']
                output['aws_access_key_id'] = config['secret-key-id']
                output['aws_secret_access_key'] = config['secret-access-key']
                output['aws_session_token'] = config['secret-session-token']
                output['region'] = config['region']
                output['pkey'] = config['instance-pkey']

            elif config["cloud-provider"].lower() == "azure":
                output['subscription_id'] = config['subscription-id']
                output['tenant_id'] = config['tenant-id']
                output['client_id'] = config['client-id']
                output['client_secret'] = config['client-secret']
                output['location'] = config['location']
                output['rg_name'] = config['rg-name']
                output['vm_size'] = config['vm-size']
                output['nic_id'] = config['nic-id']
                output['image_sku'] = config['image-sku']
                output['image_version'] = config['image-version']

            output['plugin'] = config.get('vm-series-plugin-version', False)
            output['content_upgrade'] = config.get('content-upgrade', False)
            output['antivirus_upgrade'] = config.get('antivirus-upgrade', False)
            output['gpcvpn_upgrade'] = config.get('global-protect-cvpn-upgrade', False)
            output['wildfire_upgrade'] = config.get('wildfire-upgrade', False)
            output['api_key'] = config.get('delicensing-api-key', False)
            output['auth_code'] = config.get('auth-code', False)
            output['sw_version'] = config['software-version']
            output['version'] = output['sw_version'].split('vm-')[1]
            output['cloud_provider'] = config["cloud-provider"].lower()
        except Exception as e:
            self.logger.error(f'Configuration file {filename} is broken. {str(e)}')
        self.logger.info(f'*** Custom Image with the following versions will be created: ***')
        self.logger.info(f'PanOS: {output["sw_version"]}')
        self.logger.info(f'Plugin: {output["plugin"]}')
        self.logger.info(f'Latest Content: {output["content_upgrade"]}')
        self.logger.info(f'Latest Anti-Virus: {output["antivirus_upgrade"]}')
        self.logger.info(f'Latest Global-Protect Clientless-VPN: {output["gpcvpn_upgrade"]}')
        self.logger.info(f'Latest Wildfire: {output["wildfire_upgrade"]}')
        return output

    def connect_to_vmseries(self):
        tries = 6
        host = self.cloud_client.ip
        try:
            if self.config['cloud_provider'] == 'aws':
                handler = PanosDevice(self.logger, host=host,
                                      user=self.cloud_client.config["username"],
                                      ssh_key_file=self.cloud_client.config["pkey"])
            elif self.config['cloud_provider'] == 'azure':
                handler = PanosDevice(self.logger, host=host,
                                      user=self.cloud_client.config["username"],
                                      password=self.cloud_client.config["password"])
        except Exception as e:
            self.logger.info(f'{e}')
            self.logger.info(f'Device not ready. Waiting {FIRST_WAIT}s for device to boot...')
            time.sleep(FIRST_WAIT)
            while tries != 0:
                handler = None
                try:
                    if self.config['cloud_provider'] == 'aws':
                        handler = PanosDevice(self.logger, host=host,
                                              user=self.cloud_client.config["username"],
                                              ssh_key_file=self.cloud_client.config["pkey"])
                    elif self.config['cloud_provider'] == 'azure':
                        handler = PanosDevice(self.logger, host=host,
                                              user=self.cloud_client.config["username"],
                                              password=self.cloud_client.config["password"])
                    break
                except:
                    self.logger.info(f'Management Plane not Ready. Waiting {INTERVAL}s to retry...')
                    time.sleep(INTERVAL)
                    tries -= 1
        self.logger.info('*** VM-Series Instance is up and running ***')
        self.handler = handler
        return self.handler

    def license_firewall(self):
        if self.config['auth_code']:
            self.handler.license(self.config['auth_code'])
        else:
            self.logger.info(f'*** License Auth-code not provided. Skipping Licensing Step. ***')

    def verify_system(self):
        self.handler.verify_system()

    def upgrade_plugin(self):
        if self.config["plugin"]:
            try:
                self.logger.info(f'*** Checking for Available Plugins ***')
                self.handler.exec('request plugins check')

                self.logger.info(f'*** Downloading {self.config["plugin"]} ***')
                plugin_job = self.handler.exec(
                    f'request plugins download file {self.config["plugin"]}').job_id()
                self.handler.check_job(plugin_job)
                self.logger.info(f'*** {self.config["plugin"]} Download Complete ***')

                self.logger.info(f'*** Installing {self.config["plugin"]} ***')
                plugin_job = self.handler.exec(
                    f'request plugins install {self.config["plugin"]}').job_id()
                self.handler.check_job(plugin_job)
                self.logger.info(f'*** {self.config["plugin"]} Installation Complete ***')
            except Exception as e:
                self.logger.error(f'Plugin upgrade failed!')
                self.logger.error(f'{e}')
                raise Exception(f'Plugin upgrade failed!')
        else:
            self.logger.info(f'*** Plugin Installation not requested. Skipping Step. ***')

    def upgrade_content(self):
        if self.config["content_upgrade"]:
            try:
                self.logger.info(f'*** Checking for Available Content ***')
                self.handler.exec('request content upgrade check')

                self.logger.info(f'*** Downloading Latest Content ***')
                content_job = self.handler.exec(
                    f'request content upgrade download latest').job_id()
                self.handler.check_job(content_job)
                self.logger.info(f'*** Content Download Complete ***')

                self.logger.info(f'*** Installing Latest Content ***')
                content_job = self.handler.exec(
                    f'request content upgrade install version latest').job_id()
                self.handler.check_job(content_job)
                self.logger.info(f'*** Content Installation Complete ***')
            except Exception as e:
                self.logger.error(f'Content upgrade failed!')
                self.logger.error(f'{e}')
                raise Exception(f'Content upgrade failed!')
        else:
            self.logger.info(f'*** Content Upgrade not requested. Skipping Step. ***')

    def upgrade_antivirus(self):
        try:
            if self.config["antivirus_upgrade"]:
                self.logger.info(f'*** Checking for Available Anti-virus ***')
                self.handler.exec('request anti-virus upgrade check')

                self.logger.info(f'*** Downloading Latest Antivirus ***')
                av_job = self.handler.exec(
                    f'request anti-virus upgrade download latest').job_id()

                self.handler.check_job(av_job)
                self.logger.info(f'*** Antivirus Download Complete ***')

                self.logger.info(f'*** Installing Latest Antivirus ***')
                av_job = self.handler.exec(
                    f'request anti-virus upgrade install version latest').job_id()

                self.handler.check_job(av_job)
                self.logger.info(f'*** Antivirus Installation Complete ***')
            else:
                self.logger.info(f'*** Antivirus Upgrade not requested. Skipping Step. ***')
        except Exception as e:
            self.logger.error(f'*** Unable to upgrade anti-virus; Skipping step *** ')
            self.logger.error(f'{str(e)}')

    def upgrade_gp_cvpn(self):
        try:
            if self.config["gpcvpn_upgrade"]:
                self.logger.info(f'*** Checking for Available Global-Protect Clientless-VPN ***')
                self.handler.exec('request global-protect-clientless-vpn upgrade check')

                self.logger.info(f'*** Downloading Latest Global-Protect Clientless-VPN ***')
                gp_job = self.handler.exec(
                    f'request global-protect-clientless-vpn upgrade download latest').job_id()

                self.handler.check_job(gp_job)
                self.logger.info(f'*** Global-Protect Clientless-VPN Download Complete ***')

                self.logger.info(f'*** Installing Latest Global-Protect Clientless-VPN ***')
                gp_job = self.handler.exec(
                    f'request global-protect-clientless-vpn upgrade install version latest').job_id()

                self.handler.check_job(gp_job)
                self.logger.info(f'*** Global-Protect Clientless-VPN Installation Complete ***')
            else:
                self.logger.info(f'*** Global-Protect Clientless-VPN Upgrade not requested. Skipping Step. ***')
        except Exception as e:
            self.logger.error(f'*** Unable to upgrade Global-Protect Clientless-VPN; Skipping step *** ')
            self.logger.error(f'{str(e)}')

    def upgrade_wildfire(self):
        try:
            if self.config["wildfire_upgrade"]:
                self.logger.info(f'*** Checking for Available Wildfire ***')
                self.handler.exec('request wildfire upgrade check')

                self.logger.info(f'*** Downloading Latest Wildfire ***')
                wf_job = self.handler.exec(
                    f'request wildfire upgrade download latest').job_id()

                self.handler.check_job(wf_job)
                self.logger.info(f'*** Wildfire Download Complete ***')

                self.logger.info(f'*** Installing Latest Wildfire ***')
                wf_job = self.handler.exec(
                    f'request wildfire upgrade install version latest').job_id()

                self.handler.check_job(wf_job)
                self.logger.info(f'*** Wildfire Installation Complete ***')
            else:
                self.logger.info(f'*** Wildfire Upgrade not requested. Skipping Step. ***')
        except Exception as e:
            self.logger.error(f'*** Unable to upgrade Wildfire; Skipping step *** ')
            self.logger.error(f'{str(e)}')

    def upgrade_panos(self):
        if self.config["sw_version"]:
            try:
                self.logger.info(f'*** Checking for Available PANOS Versions ***')
                self.handler.exec('request system software check')

                self.logger.info(f'*** Downloading {self.config["sw_version"]} ***')
                sw_dw_job = self.handler.exec(
                    f'request system software download file {self.config["sw_version"]}').job_id()
                self.handler.check_job(sw_dw_job)
                self.logger.info(f'*** {self.config["sw_version"]} Download Complete ***')

                self.logger.info(f'*** Installing {self.config["sw_version"]} ***')
                sw_dw_job = self.handler.exec(
                    f'request system software install version {self.config["version"]}').job_id()
                self.handler.check_job(sw_dw_job)
                self.logger.info(f'*** {self.config["sw_version"]} Installation Complete ***')

            except Exception as e:
                self.logger.error(f'PanOS upgrade failed!')
                self.logger.error(f'{e}')
                raise Exception(f'PanOS upgrade failed!')

            try:
                # Restarting System after install
                self.handler.restart_system()
            except Exception as e:
                self.logger.error(f'System Unreachable after Software install!')
                self.logger.error(f'{e}')
                raise Exception(f'System Unreachable after Software install!')

        else:
            raise Exception('"software-version" config variable cannot be empty.')

    def verify_upgrades(self, when="before"):
        if self.config["cloud_provider"].lower() == "azure" and when == "after":
            return
        else:
            self.handler.verify_versions(sw=self.config["version"],
                                         plugin=self.config["plugin"])

    def private_data_reset(self):
        if self.config['api_key']:
            self.handler.delicense(self.config['api_key'])
        else:
            self.logger.info(f'*** De-licensing API Key not provided. Skipping De-licensing Step. ***')
        self.handler.private_data_reset(self.config["cloud_provider"])

    def create_custom_image(self):
        self.logger.info(f'*** Stopping Instance ***')
        self.cloud_client.stop_instance()
        self.logger.info(f'*** Instance Stopped ***')

        self.logger.info(f'*** Creating Custom Image ***')
        self.cloud_client.create_image(name=f'PanOS-{self.config["version"]}-CustomImage')
        self.logger.info(f'*** Custom Image Creation Complete ***')
