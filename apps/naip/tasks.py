from naip.models import NAIPQuadrangle


def ingest_naip_prefix(prefix):
    """
    Compute attributes based on prefix.
    Prefix example:
    al/2013/1m/fgdc/30086/m_3008601_nw_16_1_20130928.tif
    fom naip.tasks import ingest_naip_index; from naip.models import NAIPQuadrangle; NAIPQuadrangle.objects.all().delete(); ingest_naip_index('/tmp/naip_manifest_s3.txt')
    """
    try:
        # Compute attributes based on prefix.
        # Prefix example:
        # al/2013/1m/fgdc/30086/m_3008601_nw_16_1_20130928.tif
        # from naip.tasks import ingest_naip_index; from naip.models import NAIPQuadrangle; NAIPQuadrangle.objects.all().delete(); ingest_naip_index('/tmp/naip_manifest_s3.txt')
        state, year, resolution, source, quad, filename = prefix.split('/')
        filename = filename.split('.tif')[0]
        # Get lat lon integer values.
        lat = int(quad[:2])
        lon = -int(quad[2:])

        filename_split = filename.split('_')

        if len(filename_split) == 6:
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
        print('Failed', prefix)
        raise


def ingest_naip_index(path):
    with open(path) as fl:
        bulk = []
        counter = 0
        for line in fl:
            if line.endswith('.tif\n'):
                prefix = line.split('\n')[0]
                naip = ingest_naip_prefix(prefix)
                bulk.append(naip)
                counter += 1
            if len(bulk) == 2500:
                print('Creating objects.', counter)
                NAIPQuadrangle.objects.bulk_create(bulk)
                bulk = []
        # Create the remaining objects.
        NAIPQuadrangle.objects.bulk_create(bulk)
