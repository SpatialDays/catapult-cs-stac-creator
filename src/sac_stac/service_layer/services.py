import json
import logging
import re
from shapely.geometry import Polygon
from pathlib import Path

from geopandas import GeoSeries
from pystac import Catalog, Extent, SpatialExtent, TemporalExtent, Asset, MediaType, STAC_IO
from pystac.extensions.eo import Band

from sac_stac.adapters.repository import S3Repository, NoObjectError
from sac_stac.domain.model import SacCollection, SacItem
from sac_stac.domain.operations import obtain_date_from_filename, get_geometry_from_cog, \
    get_projection_from_cog
from sac_stac.service_layer.operations import get_iso

from sac_stac.load_config import config, LOG_LEVEL, LOG_FORMAT, get_s3_configuration

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)
logger = logging.getLogger(__name__)

S3_ENDPOINT = get_s3_configuration()["endpoint"]
S3_BUCKET = get_s3_configuration()["bucket"]
S3_STAC_KEY = get_s3_configuration()["stac_key"]
S3_CATALOG_KEY = f"{S3_STAC_KEY}/catalog.json"
S3_HREF = f"{S3_ENDPOINT}/{S3_BUCKET}"
GENERIC_EPSG = 4326


def add_stac_collection(repo: S3Repository, sensor_key: str, update_collection_on_item: bool = True):
    STAC_IO.read_text_method = repo.stac_read_method

    try:
        catalog_dict = repo.get_dict(bucket=S3_BUCKET, key=S3_CATALOG_KEY)
        catalog = Catalog.from_dict(catalog_dict)
    except Exception:
        logger.info(f"No catalog found in {S3_CATALOG_KEY}")
        logger.info("Creating new catalog...")
        catalog = Catalog(
            id=config.get('id'),
            title=config.get('title'),
            description=config.get('description'),
            stac_extensions=config.get('stac_extensions')
        )

    sensor_name = sensor_key.split('/')[-2]
    sensor_configs = [s for s in config.get('sensors')]
    try:
        sensor_conf = [s for s in sensor_configs if s.get('id') == sensor_name][0]
    except IndexError:
        logger.warning(f"No config found for {sensor_name} sensor")
        return 'collection', None

    collection_key = f"{S3_STAC_KEY}/{sensor_name}/collection.json"
    try:
        repo.get_dict(bucket=S3_BUCKET, key=collection_key)
        logger.info(f"Collection {sensor_name} already exists in {collection_key}")
    except Exception:
        logger.info(f"Creating {sensor_name} collection...")
        collection = SacCollection(
            id=sensor_conf.get('id'),
            title=sensor_conf.get('title'),
            description=sensor_conf.get('description'),
            extent=Extent(SpatialExtent([[0, 0, 0, 0]]), TemporalExtent([["", ""]])),
            properties={}
        )

        collection.add_providers(sensor_conf)
        collection.add_product_definition_extension(
            product_definition=sensor_conf.get('extensions').get('product_definition'),
            bands_metadata=sensor_conf.get('extensions').get('eo').get('bands')
        )

        catalog.add_child(collection)
        catalog.normalize_hrefs(f"{S3_HREF}/{S3_STAC_KEY}")

        # TODO: Replace STAC_IO.write_text_method
        repo.add_json_from_dict(
            bucket=S3_BUCKET,
            key=S3_CATALOG_KEY,
            stac_dict=catalog.to_dict()
        )

        repo.add_json_from_dict(
            bucket=S3_BUCKET,
            key=collection_key,
            stac_dict=collection.to_dict()
        )
        logger.info(f"{sensor_name} collection added to {S3_CATALOG_KEY}")

    acquisition_keys = repo.get_acquisition_keys(bucket=S3_BUCKET,
                                                 acquisition_prefix=sensor_key)
    for acquisition_key in acquisition_keys:
        try:
            add_stac_item(repo=repo, acquisition_key=acquisition_key, update_collection_on_item=update_collection_on_item)
        except Exception as e:
            logger.warning(f"could not add {acquisition_key}: {e}")

    return 'collection', collection_key


def add_stac_item(repo: S3Repository, acquisition_key: str, update_collection_on_item: bool = True):
    STAC_IO.read_text_method = repo.stac_read_method

    sensor_name = acquisition_key.split('/')[-3]
    region = acquisition_key.split('/')[-4]
    collection_key = f"{S3_STAC_KEY}/{sensor_name}/collection.json"
    logger.debug(f"[Item] Adding {acquisition_key} item to {sensor_name}...")

    try:
        collection_dict = repo.get_dict(bucket=S3_BUCKET, key=collection_key)
        collection = SacCollection.from_dict(collection_dict)

        item_id = acquisition_key.split('/')[-2]
        item_key = f"{S3_STAC_KEY}/{collection.id}/{item_id}/{item_id}.json"
        try:
            repo.get_dict(bucket=S3_BUCKET, key=item_key)
            logger.info(f"Item {item_id} already exists in {item_key}")
        except Exception:
            sensor_conf = [s for s in config.get('sensors') if s.get('id') == collection.id][0]
            logger.debug(f"[Item] Creating {item_id} item...")
            # Get date from acquisition name
            date = obtain_date_from_filename(
                file=acquisition_key,
                regex=sensor_conf.get('formatting').get('date').get('regex'),
                date_format=sensor_conf.get('formatting').get('date').get('format')
            )

            # Get sample product and extract geometry
            try:
                product_sample_key = repo.get_smallest_product_key(
                    bucket=S3_BUCKET,
                    products_prefix=acquisition_key
                )
                product_sample_href = f"{S3_HREF}/{product_sample_key}"
                geometry, crs = get_geometry_from_cog(product_sample_href)
            except Exception:
                logger.error(f"No bands found on {acquisition_key} acquisition.")
                raise

            item = SacItem(
                id=Path(acquisition_key).name,
                datetime=date,
                geometry=create_geom(geometry, crs).get('features')[0].get('geometry'),
                bbox=list(geometry.bounds),
                properties={}
            )

            item.ext.enable('projection')
            item.ext.projection.epsg = GENERIC_EPSG
    
            item.add_extensions(sensor_conf.get('extensions'))
            item.add_common_metadata(sensor_conf.get('common_metadata'))

            bands_metadata = sensor_conf.get('extensions').get('eo').get('bands')
            product_keys = repo.get_product_keys(bucket=S3_BUCKET, products_prefix=acquisition_key)

            for band_name, band_common_name in [(b.get('name'), b.get('common_name')) for b in bands_metadata]:
                asset_href = ''
                proj_shp = [0, 0]
                proj_tran = [0, 0, 0, 0, 0, 0]

                band_name_in_product_keys = [p for p in product_keys if re.search(band_name, p, re.IGNORECASE)]

                if band_name_in_product_keys:
                    product_key = band_name_in_product_keys[0]
                    asset_href = f"{S3_HREF}/{product_key}"
                    proj_shp, proj_tran = get_projection_from_cog(asset_href)
                else:
                    logger.warning(f"No band matching \"{band_name}\" found on {collection.id}/{item.id} acquisition.")
                    continue  # don't try and add unknown bands

                asset = Asset(
                    href=asset_href,
                    media_type=MediaType.COG
                )

                # Set Projection
                item.ext.projection.set_transform(proj_tran, asset)
                item.ext.projection.set_shape(proj_shp, asset)

                # Set bands
                item.ext.eo.set_bands([Band.create(
                    name=band_common_name, common_name=band_common_name)],
                    asset
                )
                logger.debug(f"[Asset] Adding {asset_href} asset to {acquisition_key}...")
                item.add_asset(key=band_common_name, asset=asset)

            if sensor_conf.get('extensions').get('odc'):
                item.ext.enable('odc')
                item.ext.odc.region_code = get_iso(region)
            
            collection.add_item(item)
            
            if update_collection_on_item:
                collection.update_extent_from_items()
                collection.normalize_hrefs(f"{S3_HREF}/{S3_STAC_KEY}/{collection.id}")
            
            repo.add_json_from_dict(
                bucket=S3_BUCKET,
                key=collection_key,
                stac_dict=collection.to_dict()
            )
                
            # TODO: Replace STAC_IO.write_text_method
            repo.add_json_from_dict(
                bucket=S3_BUCKET,
                key=item_key,
                stac_dict=item.to_dict()
            )
            logger.info(f"{item.id} item added to {collection.id}")

        return 'item', item_key

    except TypeError:
        logger.error(f"Invalid collection in {collection_key}, "
                     f"could not add {acquisition_key}.")
        return 'item', None
    except KeyError:
        logger.error(f"No collection found in {collection_key},"
                     f"could not add {acquisition_key}.")
        return 'item', None
    except NoObjectError as e:
        logger.error(f"Could not find object in S3: {e}")
        return 'item', None


def create_geom(geometry, crs):

    if isinstance(geometry, Polygon):
        poly = GeoSeries([geometry.exterior], crs=crs).to_crs(GENERIC_EPSG).to_json()
    else:
        poly = GeoSeries([geometry], crs=crs).to_crs(GENERIC_EPSG).to_json()
    result = json.loads(poly)
    return result
