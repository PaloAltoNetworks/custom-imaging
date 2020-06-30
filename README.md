# Custom Imaging
Create custom VM-Series images on public cloud with upgraded PanOS, Plugin and Content versions

## Support Policy
The code and script in the repo are released under an as-is, best effort, support policy. These scripts should be seen as community supported and Palo Alto Networks will contribute our expertise as and when possible. We do not provide technical support or help in using or troubleshooting the components of the project through our normal support options such as Palo Alto Networks support teams, or ASC (Authorized Support Centers) partners and backline support options. The underlying product used (the VM-Series firewall) by the scripts are still supported, but the support is only for the product functionality and not for help in deploying or using the script itself.
Unless explicitly tagged, all projects or work posted in our GitHub repository (at https://github.com/PaloAltoNetworks) or sites other than our official Downloads page on https://support.paloaltonetworks.com are provided under the best effort policy.

## AWS Custom AMI
#### Notes:
  - Only upgrades among major releases are supported. For example, upgrade from **9.0**.1 to **9.0**.6 is supported, upgrade from **8.1**.4 to **9.0**.6 is not supported.
  - Script takes VM-Series EC2 instance details and upgrade configuration as input and creates an AMI based on the upgrade configuration.
  - Steps 1 to 6 followed in [Custom AMI Documentation] have been automated in this script.
  - Script runs for approximately 90 minutes.

#### Steps:

  1. On AWS, create a VPC with Internet Gateway and a subnet. Save the subnet-id for use.
  2. Create a Key Pair in EC2. Save the key name and private key file for use.([Create Key-pair])
  3. Get the AMI-ID for the marketplace image that you want to start as a base instance.([Obtain the AMI])
  4. Prepare an auth-code for VM-Series to allow upgrade.(BYOL only)
  5. Set up a Unix/Linux machine/virtual-machine with internet access to run the script from.
  6. On AWS, create a security group and allow inbound TCP-port 22 connections from machine/virtual-machine public IP(Created in Step 5). This is to allow the script to access the VM-Series EC2 Instance.
  7. Install Python 3.6.10 and git on the machine/virtual-machine.
  8. Clone the Palo Alto Networks custom-imaging repository in the machine/virtual-machine.
  `git@github.com:PaloAltoNetworks/custom-imaging.git`
  9. Copy the private key file(from STEP 2) to the machine/virtual-machine with correct permissions.
  `chmod 400 private_key.pem` 
  10. Enter the directory customami. 
  `cd custom-imaging` 
  11. Install the requirements.
  `pip install -r requirements.txt`
  12. Edit config.yaml file based on your requirement of the following AWS and PanOS parameters:

| Keys | Requirement |  Explanation | Sample Values |
| ------ | ------ | ------ | ------ |
| secret-key-id | mandatory | AWS Secret Access Key ID | secret-key-id: 'AK****************XH' |
| secret-access-key | mandatory | AWS Secret Access Key | secret-access-key: 'Bh******************i3' |
| region | mandatory | AWS Region for Custom AMI Creation | region: 'us-west-1' |
| ami-id | mandatory | Your AMI-ID from Step 3 | ami-id: 'ami-03801628148e17514' |
| mgmt-subnet-id | mandatory | Subnet ID from Step 1 | mgmt-subnet-id: 'subnet-04fbcf63f1cc4fffc' |
| sg-id | mandatory | Security Group ID from Step 6 | sg-id: 'sg-0bc54b68a3ff9c226' |
| key-pair-name | mandatory | Key Pair Name from Step 2 | key-pair-name: 'my-key-pair' |
| instance-type | mandatory | AWS Instance Type: Depends on AWS region available instance types and Vm-Series license | instance-type: 'm5.xlarge' |
| instance-pkey | mandatory | On machine/virtual-machine, absolute path to private key from Step 9 | instance-pkey: '/path/to/directory/custom_ami/private_key.pem' |
| auth-code | optional | VM-Series auth code for licensing. Not required for Bundle1 and Bundle2 AMIs. | auth-code: 'M0101010' #For BYOL Deployment Only<br/>auth-code: false # For Bundle/PAYG Deployment Only|
| delicensing-api-key | optional | Delicensing API key. Not required for Bundle1 and Bundle2 AMIs. Required for BYOL AMI only. | delicensing-api-key: '6*********************d' # For BYOL <br/>delicensing-api-key: false # For Bundle/PAYG Deployment Only|
| vm-series-plugin-version | optional | Desired VM-Series Plugin version | vm-series-plugin-version: 'vm_series-1.0.11’ <br/>vm-series-plugin-version: false  # For not upgrading the plugin |
| software-version | mandatory | Desired PanOS version | software-version: 'PanOSXFR_vm-9.0.5.xfr’ <br/>software-version: 'PanOS_vm-9.1.2' |
| content-upgrade | optional | Boolean Value | content-upgrade: true # To upgrade content <br/>content-upgrade: false # To not upgrade content |
| antivirus-upgrade | optional | Boolean Value | antivirus-upgrade: true # To upgrade Anti-Virus <br/>antivirus-upgrade: false # To not upgrade Anti-Virus
| global-protect-cvpn-upgrade | optional | Boolean Value | global-protect-cvpn-upgrade: true # To upgrade Global-Protect Clientless-VPN <br/>global-protect-cvpn-upgrade: false # To not upgrade Global-Protect Clientless-VPN |
| wildfire-upgrade | optional | Boolean Value | wildfire-upgrade: true # To upgrade Wildfire <br/>wildfire-upgrade: false # To not upgrade Wildfire
  
  13. Execute the script.
  `python start.py`
  14. Once the script completes, it will dump a new AMI in the region configured in config.yaml file.


   [Custom AMI Documentation]: https://docs.paloaltonetworks.com/vm-series/9-0/vm-series-deployment/set-up-the-vm-series-firewall-on-aws/deploy-the-vm-series-firewall-on-aws/create-custom-ami.html
   [Create Key-pair]: <https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-key-pairs.html#having-ec2-create-your-key-pair>
   [Obtain the AMI]: <https://docs.paloaltonetworks.com/content/techdocs/en_US/vm-series/7-1/vm-series-deployment/set-up-the-vm-series-firewall-in-aws/obtain-the-ami.html#36825>
