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
