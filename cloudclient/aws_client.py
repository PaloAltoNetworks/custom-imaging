
import os
import time

import boto3


class CloudAws(object):
    def __init__(self, logger, config):
        self.name = 'aws'
        self.region = config["region"]
        self.logger = logger
        self.config = config
        logger.info('Connecting to AWS...')
        try:
            self.client = boto3.client(
                'ec2',
                aws_access_key_id=config["aws_access_key_id"],
                aws_secret_access_key=config["aws_secret_access_key"],
                region_name=config["region"])
            self.resource = boto3.resource(
                'ec2',
                aws_access_key_id=config["aws_access_key_id"],
                aws_secret_access_key=config["aws_secret_access_key"],
                region_name=config["region"])
            self.id = os.getpid()
            logger.info('Connection Successful.')
        except Exception as e:
            logger.error(f'Unable to connect to AWS: {str(e)}')
        self.instance_id = ""
        self.public_ip = ""

    def _get_public_ip(self):
        response = self.client.describe_instances(InstanceIds=[self.instance_id])
        public_ip = response['Reservations'][0]['Instances'][0]['PublicIpAddress']
        return public_ip

    def create_instance(self):
        ami_id = self.config.get("ami_id")
        mgmt_subnet_id = self.config.get("mgmt_subnet_id")
        sg_id = self.config.get("sg_id")
        key_pair_name = self.config.get("key_pair_name")
        instance_type = self.config.get("instance_type", 'm5.xlarge')

        waiter = self.client.get_waiter('instance_running')
        self.logger.info(f'*** Creating Instance ***')
        try:
            instance_request = self.resource.create_instances(
                BlockDeviceMappings=[
                    {
                        'DeviceName': '/dev/xvda',
                        'Ebs': {
                            'DeleteOnTermination': True,
                        }
                    }
                ],
                ImageId=ami_id,
                MinCount=1,
                MaxCount=1,
                KeyName=key_pair_name,
                InstanceType=instance_type,
                NetworkInterfaces=[
                    {
                        'DeviceIndex': 0,
                        'AssociatePublicIpAddress': True,
                        'SubnetId': mgmt_subnet_id,
                        'Groups': [sg_id, ],
                    }
                ]
            )
            time.sleep(30)
            instance_id = instance_request[0].id
            waiter.wait(InstanceIds=[instance_id])
            self.logger.info('*** Instance Creation Successful ***')
            self.resource.create_tags(Resources=[instance_id], Tags=[{
                'Key': 'Name', 'Value': f'CI_Generator_{self.id}'}
            ])
        except Exception as e:
            self.logger.error(f'ERROR: Unable to deploy the instance: {str(e)}')
        self.instance_id = instance_id
        self.public_ip = self._get_public_ip()
        return {'instance_id': instance_id, 'ip': self.public_ip, 'user': 'admin'}

    def terminate_instance(self):
        waiter = self.client.get_waiter('instance_terminated')
        self.client.terminate_instances(InstanceIds=[self.instance_id])
        self.logger.info('Waiting for completion...')
        time.sleep(20)
        try:
            waiter.wait(InstanceIds=[self.instance_id])
        except BaseException:
            self.logger.error('Unable to terminate instance.')
        return

    def stop_instance(self):
        waiter = self.client.get_waiter('instance_stopped')
        stop_request = self.client.stop_instances(InstanceIds=[self.instance_id])
        self.logger.info(f'Stopping instance {self.instance_id} ...')
        try:
            waiter.wait(InstanceIds=[self.instance_id])
            stop_result = True
            self.logger.info('Instance stopped.')
        except BaseException:
            stop_result = False
            self.logger.error('Unable to stop instance.')
        return stop_result

    def create_image(self, name):
        waiter = self.client.get_waiter('image_available')
        create_request = self.client.create_image(InstanceId=self.instance_id,
                                                  NoReboot=False,
                                                  Name=f'{name}-{self.id}',
                                                  Description='Custom Image created by Palo Alto Networks')
        ami_id = create_request["ImageId"]
        self.logger.info(f'Waiting for the custom AMI {ami_id} to be available.')
        try:
            waiter.wait(ImageIds=[ami_id])
            result = True
            self.logger.info(f'Custom AMI: {ami_id} has been created in region: {self.region}.')
        except BaseException:
            self.logger.error('Unable to check availability of the new AMI.')
            result = False
        return result
