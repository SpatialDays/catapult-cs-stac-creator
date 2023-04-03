import asyncio
import logging
import signal
import os
import redis

from nats.aio.client import Client as NATS
from sac_stac.adapters import repository
from sac_stac.domain.s3 import S3
from sac_stac.service_layer.services import add_stac_collection, add_stac_item
from sac_stac.load_config import get_nats_uri, LOG_LEVEL, LOG_FORMAT, get_s3_configuration

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)

logger = logging.getLogger(__name__)

S3_ACCESS_KEY_ID = get_s3_configuration()["key_id"]
S3_SECRET_ACCESS_KEY = get_s3_configuration()["access_key"]
S3_REGION = get_s3_configuration()["region"]
S3_ENDPOINT = get_s3_configuration()["endpoint"]

s3 = S3(key=S3_ACCESS_KEY_ID, secret=S3_SECRET_ACCESS_KEY, s3_endpoint=S3_ENDPOINT, region_name=S3_REGION)

# async def run(nc, repo, loop):

#     async def closed_cb():
#         logger.info("Connection to NATS is closed.")
#         await asyncio.sleep(0.1, loop=loop)
#         loop.stop()

#     options = {
#         "servers": [get_nats_uri()],
#         "loop": loop,
#         "closed_cb": closed_cb
#     }

#     await nc.connect(**options)
#     logger.info(f"Connected to NATS at {nc.connected_url.netloc}...")

#     async def message_handler(msg):
#         subject = msg.subject
#         data = msg.data.decode()
#         logger.info(f"Received a message on '{subject}': {data}")
#         r = {
#             'collection': add_stac_collection,
#             'item': add_stac_item
#         }
#         logger.info(f"Handling message - 1")
#         message_type = subject.split('.')[1]
#         logger.info(f"message_type {message_type}")
#         if message_type in r.keys():
#             logger.info(f"Processing {message_type} message 1")
#             for k, v in r.items():
#                 logger.info(f"Processing {k} message now")
#                 if k in subject:
#                     logger.info(f"Handling message - 2")
#                     logger.info(f"Calling function {v}")
#                     stac_type, key = v(repo, data)
#                     logger.info(f"Added {stac_type} {key} to repository")
#                     if key:
#                         subj = f'stac_indexer.{stac_type}'
#                         msg = key.encode()
#                         logger.info(f"Publishing {subj} {msg}")
#                         await nc.publish(subj, msg)
#                         logger.info(f"Published a message on '{subj}': {msg.decode()}")

#     await nc.subscribe("stac_creator.*", cb=message_handler)

#     def signal_handler():
#         if nc.is_closed:
#             return
#         logger.info("Disconnecting...")
#         loop.create_task(nc.close())

#     for sig in ('SIGINT', 'SIGTERM'):
#         loop.add_signal_handler(getattr(signal, sig), signal_handler)


if __name__ == '__main__':

    repo = repository.S3Repository(s3)

    REDIS_PORT = os.getenv('REDIS_PORT', 6379)
    REDIS_HOST = os.getenv('REDIS_HOST', 'localhost')

    redis = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

    REDIS_QUEUE_COLLECTIONS = "stac_creator_collection_list"
    REDIS_QUEUE_ITEMS = "stac_creator_items_list"

    while True:
        # if you have something in collections, process it first
        while redis.llen(REDIS_QUEUE_COLLECTIONS) > 0:
            data = redis.lpop(REDIS_QUEUE_COLLECTIONS)
            data = data.decode()
            logger.info(f"Received a message on stac_creator_collection_list: {data}")
            _, key = add_stac_collection(repo, str(data))
            if key:
                msg = key.encode()
                logger.info(f"Publishing stac_indexer_collection_list {msg}")
                redis.rpush("stac_indexer_collection_list", msg)
                logger.info(f"Published a message on stac_indexer_collection_list: {msg.decode()}")
        # if you have something in items, process it
        if redis.llen(REDIS_QUEUE_ITEMS) > 0:
            data = redis.lpop(REDIS_QUEUE_ITEMS)
            data = data.decode()
            logger.info(f"Received a message on stac_creator_items_list: {data}")
            _, key = add_stac_item(repo, str(data))
            if key:
                msg = key.encode()
                logger.info(f"Publishing stac_indexer_item_list {msg}")
                redis.rpush("stac_indexer_item_list", msg)
                logger.info(f"Published a message on stac_indexer_item_list: {msg.decode()}")
