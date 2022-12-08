import json
import os
import logging
from pathlib import Path

LOG_FORMAT = '%(asctime)s - %(levelname)6s - %(message)s'
LOG_LEVEL = logging.getLevelName(os.getenv("LOG_LEVEL", "INFO"))

with open(Path(__file__).parent / "config.json") as json_data_file:
    config_file = json.load(json_data_file)

config = config_file


def get_nats_uri():
    host = os.environ.get("NATS_HOST", "127.0.0.1")
    port = os.environ.get("NATS_PORT", "4222")
    return f"nats://{host}:{port}"


def get_s3_configuration():
    key_id = os.environ.get("AWS_ACCESS_KEY_ID", '')
    access_key = os.environ.get("AWS_SECRET_ACCESS_KEY", '')
    region = os.environ.get("AWS_DEFAULT_REGION", 'us-east-1')
    endpoint = os.environ.get("S3_ENDPOINT", '')
    bucket = os.environ.get("S3_BUCKET", '')
    imagery_path = os.environ.get("S3_IMAGERY_PATH", '')
    stac_path = os.environ.get("S3_STAC_PATH", '')
    return dict(key_id=key_id, access_key=access_key, region=region,
                endpoint=endpoint, bucket=bucket, stac_path=stac_path, imagery_path=imagery_path)
