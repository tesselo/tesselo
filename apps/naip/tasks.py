import logging
import os

import boto3

from naip.models import NAIPQuadrangle

logger = logging.getLogger('django')


def ingest_naip_prefix(prefix):
    """
    Compute attributes based on prefix.
    Prefix example:
    al/2013/1m/fgdc/30086/m_3008601_nw_16_1_20130928.mrf
    """
    try:
        # Compute attributes based on prefix.
        # Prefix example:
        # al/2013/1m/fgdc/30086/m_3008601_nw_16_1_20130928.mrf
        state, year, resolution, source, quad, filename = prefix.split('/')
        filename = filename.split('.mrf')[0]
        # Get lat lon integer values.
        lat = int(quad[:2])
        lon = -int(quad[2:])

        filename_split = filename.split('_')
        if len(filename_split) == 7:
            dat, subquad, corner, misc1, misc2, date, version = filename_split
            date = '{}-{}-{}'.format(date[:4], date[4:6], date[6:])
        elif len(filename_split) == 6:
            dat, subquad, corner, misc1, misc2, date = filename_split
            date = '{}-{}-{}'.format(date[:4], date[4:6], date[6:])
        elif len(filename_split) == 5:
            dat, subquad, corner, misc1, misc2 = filename_split
            date = '{}-01-01'.format(year)
        else:
            # Some file names do not contain dates. Log first day of the year as
            # date in that case.
            subquad, corner, misc1, misc2 = filename.split('_')
            date = '{}-01-01'.format(year)

        # Subquad index within the 8x8 subquads.
        subquad = subquad[-2:]

        return NAIPQuadrangle(
            prefix=prefix,
            state=state,
            resolution=resolution,
            source=source,
            corner=corner,
            subquad=subquad,
            lat=lat,
            lon=lon,
            date=date,
        )
    except:
        logger.info('Failed', prefix)
        raise


def ingest_naip_manifest():
    # Get current manifest file.
    logger.info('Getting manifest file.')
    s3 = boto3.resource('s3')
    s3.Object('naip-analytic', 'manifest.txt').download_file('/tmp/manifest.txt', ExtraArgs={'RequestPayer': 'requester'})
    # Delete all existing naip quadrangles.
    NAIPQuadrangle.objects.all().delete()
    # Ingest naip quadrangles line by line.
    with open('/tmp/manifest.txt') as fl:
        bulk = []
        counter = 0
        for line in fl:
            if line.endswith('.mrf\n'):
                prefix = line.split('\n')[0]
                naip = ingest_naip_prefix(prefix)
                bulk.append(naip)
                counter += 1
            if len(bulk) == 2500:
                logger.info('Creating objects.', counter)
                NAIPQuadrangle.objects.bulk_create(bulk)
                bulk = []
        # Create the remaining objects.
        NAIPQuadrangle.objects.bulk_create(bulk)
    # Remove naip manifest.
    os.remove('/tmp/manifest.txt')
