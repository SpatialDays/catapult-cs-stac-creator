import logging
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Tuple
from sac_stac.adapters.repository import S3Repository
import rasterio
from rasterio import RasterioIOError
from rasterio.crs import CRS
from shapely.geometry import box, Polygon

from sac_stac.load_config import LOG_LEVEL, LOG_FORMAT
from sac_stac.load_config import get_s3_configuration

from sac_stac.util import extract_common_prefix, parse_s3_url
S3_BUCKET = get_s3_configuration()["bucket"]

logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT)

logger = logging.getLogger(__name__)


def obtain_date_from_filename(file: str, regex: str, date_format: str) -> datetime:
    """
    Return date from given file based on regular expression and date format.

    :param file: path to file
    :param regex: regular expression to search in filename
    :param date_format: format used when converting to datetime

    :return: datetime object with obtained date.
    """
    filename = Path(file).name
    match_date = re.search(regex, filename)
    date = None

    if match_date:
        date = datetime.strptime(match_date.group(1), date_format)

    return date


def get_geometry_from_cog(cog_url: str = None, cog_key:str = None, s3_repository:S3Repository = None) -> Tuple[Polygon, CRS]:
    """
    Extract geometry information out of the COG file served under
    the given url.

    :param cog_url: url to cog file

    :return: A Polygon and CRS objects.
    """
    if os.environ.get("TEST_ENV"):
        bucket, key = parse_s3_url(cog_url)
        cog_url = f"tests/data/{key}"
    logging.info("cog_url: %s", cog_url)
    try:
        if not cog_key:
            with rasterio.open(cog_url) as ds:
                geom = box(*ds.bounds)
                crs = ds.crs
            return geom, crs
        else:
            new_cog_url = s3_repository.sign_file(bucket=S3_BUCKET,key=cog_key)
            with rasterio.open(new_cog_url) as ds:
                geom = box(*ds.bounds)
                crs = ds.crs
            return geom, crs
    except RasterioIOError as e:
        logger.warning(f"Error extracting geometry from {cog_url}: {e}")
        return Polygon(), CRS()


def get_projection_from_cog(cog_url: str = None, cog_key:str = None, s3_repository:S3Repository = None) -> Tuple[list, list]:
    """
    Extract projection information out of the COG file served under
    the given url.

    :param cog_url: url to cog file

    :return: A shape and transform lists.
    """
    if os.environ.get("TEST_ENV"):
        bucket, key = parse_s3_url(cog_url)
        cog_url = f"tests/data/{key}"
    try:
        if not cog_key:
            with rasterio.open(cog_url) as ds:
                return list(ds.shape), list(ds.transform)
        else:
            new_cog_url = s3_repository.sign_file(bucket=S3_BUCKET,key=cog_key)
            with rasterio.open(new_cog_url) as ds:
                return list(ds.shape), list(ds.transform)
    except RasterioIOError as e:
        logger.warning(f"Error extracting projection from {cog_url}: {e}")
        return [], []
