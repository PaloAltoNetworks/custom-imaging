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

import os
import time

from azure.identity import ClientSecretCredential
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient


class CloudAzure(object):
    def __init__(self, logger, config):
        self.name = 'azure'
        self.location = config["location"]
        self.logger = logger
        self.config = config
        logger.info('Connecting to Azure...')
        try:
            credentials = ClientSecretCredential(
                client_id=config["client_id"],
                client_secret=config["client_secret"],
                tenant_id=config["tenant_id"]
            )
            self.compute_client = ComputeManagementClient(credential=credentials,
                                                          subscription_id=config["subscription_id"])
            self.network_client = NetworkManagementClient(credential=credentials,
                                                          subscription_id=config["subscription_id"])
            self.id = os.getpid()
            logger.info('Connection Successful.')
        except Exception as e:
            logger.error(f'Unable to connect to Azure: {str(e)}')
        self.config["username"] = "panadmin"
        self.config["password"] = "P@nwCust0m!m@ge"
        self.instance_name = ""
        self.public_ip = ""

    def _get_public_ip(self):
        # instance = self.compute_client.virtual_machines.get(resource_group_name=self.config['rg_name'],
        #                                                     vm_name=self.instance_name)
        # interfaces = instance.network_profile.network_interfaces
        # ni_reference = interfaces[0]
        # ni_reference = ni_reference.id.split('/')
        ni_reference = self.config['nic_id'].split('/')
        ni_group = ni_reference[4]
        ni_name = ni_reference[8]
        net_interface = self.network_client.network_interfaces.get(ni_group, ni_name)
        ip_reference = net_interface.ip_configurations[0].public_ip_address
        ip_reference = ip_reference.id.split('/')
        ip_group = ip_reference[4]
        ip_name = ip_reference[8]
        public_ip = self.network_client.public_ip_addresses.get(ip_group, ip_name)
        public_ip = public_ip.ip_address
        return public_ip

    def create_instance(self):
        self.logger.info(f'Creating VM "PANW-CI-{self.id}" ...')
        try:
            poller = self.compute_client.virtual_machines.begin_create_or_update(self.config['rg_name'],
                                                                                 f'PANW-CI-{self.id}',
                                                                                 {
                                                                                "location": self.config['location'],
                                                                                "storage_profile": {
                                                                                    "image_reference": {
                                                                                        "publisher": "paloaltonetworks",
                                                                                        "offer": "vmseries-flex",
                                                                                        "sku": self.config["image_sku"],
                                                                                        "version":
                                                                                            self.config["image_version"]
                                                                                    }
                                                                                },
                                                                                "plan": {
                                                                                    "name": self.config["image_sku"],
                                                                                    "product": "vmseries-flex",
                                                                                    "publisher": "paloaltonetworks"
                                                                                },
                                                                                "hardware_profile": {
                                                                                    "vm_size": self.config['vm_size']
                                                                                },
                                                                                "os_profile": {
                                                                                    "computer_name":
                                                                                        f'PANW-CI-{self.id}',
                                                                                    "admin_username":
                                                                                        self.config["username"],
                                                                                    "admin_password":
                                                                                        self.config["password"]
                                                                                },
                                                                                "network_profile": {
                                                                                    "network_interfaces": [{
                                                                                        "id": self.config['nic_id'],
                                                                                        "properties": {
                                                                                            "primary": True
                                                                                        }
                                                                                    }]
                                                                                }
                                                                            }
                                                                                 )

            vm_result = poller.result()
            self.logger.debug(f'vm_result: {str(vm_result.__dict__)}')
            self.instance_name = vm_result.name
            self.public_ip = self._get_public_ip()
            self.logger.info('*** Instance Creation Successful ***')
        except Exception as e:
            self.logger.error(f'ERROR: Unable to deploy the instance: {str(e)}')
            exit(0)
        return {'instance_name': self.instance_name, 'ip': self.public_ip, 'user': 'admin'}

    def terminate_instance(self):
        try:
            poller = self.compute_client.virtual_machines.begin_delete(self.config['rg_name'], self.instance_name)
            self.logger.info('Waiting for completion...')
            time.sleep(20)
            poller.result()

            disk_list = self.compute_client.disks.list_by_resource_group(self.config['rg_name'])
            for disk in disk_list:
                if self.instance_name in disk.name:
                    async_disk_delete = self.compute_client.disks.begin_delete(self.config['rg_name'], disk.name)
                    async_disk_delete.result()
                    break

        except Exception as e:
            self.logger.error(f'Unable to terminate instance: {str(e)}')
        return

    def stop_instance(self):
        try:
            poller = self.compute_client.virtual_machines.begin_deallocate(self.config['rg_name'], self.instance_name)
            self.logger.info(f'Stopping instance {self.instance_name} ...')
            poller.result()
            stop_result = True
        except Exception as e:
            self.logger.error(f'Unable to stop instance: {str(e)}')
            stop_result = False
        self.logger.info('Instance stopped.')
        return stop_result

    def create_image(self, name):
        try:
            self.compute_client.virtual_machines.generalize(self.config['rg_name'], self.instance_name)
            self.logger.info(f'Generalizing VM instance {self.instance_name} ...')
            time.sleep(20)
        except Exception as e:
            self.logger.error(f'Unable to generalize VM instance: {str(e)}')
            return False
        self.logger.info('VM Instance Generalized.')

        instance = self.compute_client.virtual_machines.get(resource_group_name=self.config['rg_name'],
                                                            vm_name=self.instance_name)
        image_parameters = {
            "location": self.config['location'],
            "source_virtual_machine": {
                "id": instance.id
            }
        }

        try:
            poller = self.compute_client.images.begin_create_or_update(self.config['rg_name'], name, image_parameters)
            self.logger.info(f'Creating Image from VM instance {self.instance_name} ...')
            image_result = poller.result()
            image_id = image_result.id
        except Exception as e:
            self.logger.error(f'Unable to create Image from VM instance: {str(e)}')
            return False
        self.logger.info('Custom Image creation complete.')
        self.logger.info(f'Custom Image ID: {image_id}')
        return True
