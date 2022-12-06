import logging

import boto3
from botocore.exceptions import ClientError
from sac_stac.load_config import LOG_LEVEL, LOG_FORMAT

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)

logger = logging.getLogger(__name__)


class S3:
    """Class to handle S3 operations."""

    def __init__(self, key, secret, s3_endpoint, region_name):
        """
        Initialize s3 class.
        Params:
            key           (str): AWS_ACCESS_KEY_ID
            secret        (str): AWS_SECRET_ACCESS_KEY
            s3_endpoint   (str): S3 endpoint URL
            region_name   (str): Region Name
        """
        self.s3_resource = boto3.resource(
            "s3",
            endpoint_url=s3_endpoint,
        )
        self.buckets_exist = []

    def list_objects(self, bucket_name, *, prefix=None, suffix=None, limit=None):
        """
        List objects stored in a bucket.
        Params:
            bucket_name      (str): Bucket name
        Keyword arguments (opt):
            prefix           (str): Filter only objects with specific prefix
                                    default None
            suffix           (str): Filter only objects with specific suffix
                                    default None
            limit            (int): Limit the number of objects returned
                                    default None
        Returns:
            An iterable of ObjectSummary resources
        """
        paginator = self.s3_resource.meta.client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        
        objects = [self.s3_resource.ObjectSummary(bucket_name, item['Key']) for page in pages for item in page['Contents']]

        if not objects:
            raise NoObjectError(f'Nothing found with {prefix}*{suffix} in {bucket_name} bucket')

        if suffix:
            return [obj for obj in objects if obj.key.endswith(suffix)]
        else:
            return objects

    def get_object_body(self, bucket_name, object_name):
        """
        Download an object from S3 and return its body.
        Params:
            bucket_name            (str): Bucket name
            object_name            (str): Object name
        """
        try:
            obj = self.s3_resource.Object(bucket_name=bucket_name, key=object_name).get()
            return obj.get('Body').read()
        except ClientError as ex:
            if ex.response['Error']['Code'] == 'NoSuchKey':
                raise NoObjectError(f'Nothing found with {object_name} in {bucket_name} bucket')

    def put_object(self, bucket_name, key, body):
        try:
            response = self.s3_resource.Object(bucket_name=bucket_name, key=key).put(Body=body)
            return response
        except ClientError as ex:
            logger.warning(f"Could not put {key} in {bucket_name} bucket: {ex}")
            return None

    def list_common_prefixes(self, bucket_name, prefix):
        """
        List all common prefixes with the given prefix delimited by '/'.
        Params:
            bucket_name            (str): Bucket name
            prefix                 (str): Prefix
        """
        common_prefixes = []
        paginator = self.s3_resource.meta.client.get_paginator('list_objects_v2')
        pages = paginator.paginate(Bucket=bucket_name, Prefix=prefix, Delimiter='/')
        for page in pages:
            if page.get('CommonPrefixes'):
                for p in page.get('CommonPrefixes'):
                    common_prefixes.append(p.get('Prefix'))

        return common_prefixes

    def create_presigned_url(self, bucket_name,key:str):
        try:
            response = self.s3_resource.meta.client.generate_presigned_url('get_object', Params={'Bucket': bucket_name, 'Key': key}, ExpiresIn=3600)
            return response
        except ClientError as ex:
            logger.warning(f"Could not create presigned URL for {key}: {ex}")
            return None

class NoObjectError(Exception):
    pass

