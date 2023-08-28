import ibm_boto3
from ibm_botocore.client import Config, ClientError 
from blueprints.confidential import IBM_API_KEY_ID, IBM_ACCESS_KEY_ID, IBM_ENDPOINT, IBM_INSTANCE_CRN, IBM_SECRET_ACCESS_KEY

COS_ENDPOINT = IBM_ENDPOINT
COS_API_KEY_ID = IBM_API_KEY_ID
COS_INSTANCE_CRN = IBM_INSTANCE_CRN


cos = ibm_boto3.client("s3",
    ibm_api_key_id=COS_API_KEY_ID,
    ibm_service_instance_id=COS_INSTANCE_CRN,
    config=Config(signature_version="oauth"),
    endpoint_url=COS_ENDPOINT
)

cosReader = ibm_boto3.client("s3",
            aws_access_key_id=IBM_ACCESS_KEY_ID,
            aws_secret_access_key=IBM_SECRET_ACCESS_KEY,
            endpoint_url=COS_ENDPOINT
)