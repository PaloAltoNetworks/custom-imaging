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

from cloudclient.aws_client import CloudAws
from cloudclient.gcp_client import CloudGcp
from cloudclient.azure_client import CloudAzure


class CloudProvider(object):
    def __new__(cls, logger, provider_name, config):
        if provider_name.lower() in ('aws', 'amazon', 'amazon aws'):
            return CloudAws(logger, config)
        elif provider_name.lower() in ('gcp', 'google', 'google cloud',
                                       'google cloud platform'):
            return CloudGcp(logger, config)
        elif provider_name.lower() in ('azure', 'msazure', 'azure cloud',
                                       'microsoft azure'):
            return CloudAzure(logger, config)
        else:
            logger.error(
                "Public Cloud Platform '" +
                provider_name +
                "' is not supported.")
            raise Exception(
                "Public Cloud Platform '" +
                provider_name +
                "' is not supported.")
