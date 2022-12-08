# CS STAC creator

## Introduction

This tool is used along [cs-stac-indexer](https://github.com/SatelliteApplicationsCatapult/cs-stac-indexer) to generate
STAC metadata out of imagery stored in a S3 bucket.

## Environment Variables
| Var name| Used for |
| --- | --- |
|NATS_HOST | The hostname of the NATS server |
|NATS_PORT | The port of the NATS server |
|AWS_ACCESS_KEY_ID | AWS access key |
|AWS_SECRET_ACCESS_KEY | AWS secret key |
|S3_ENDPOINT_URL | S3 endpoint url |
|AWS_DEFAULT_REGION | AWS region |
|S3_BUCKET | S3 bucket name |
|S3_IMAGERY_PATH | S3 path where the imagery is stored |
|S3_STAC_PATH | S3 key where the STAC metadata will be stored |
