from collections import OrderedDict
from tempfile import TemporaryFile

import numpy
from django.contrib.gis.gdal import GDALRaster
from django.core.files import File
from raster.rasterize import rasterize
from raster.tiles.const import WEB_MERCATOR_SRID, WEB_MERCATOR_TILESIZE
from raster.tiles.utils import tile_bounds, tile_index_range

from classify.const import SCALE
from classify.models import TrainingPixels, TrainingPixelsPatch
from classify.tasks import get_rasterlayer_ids
from jobs import ecs
from sentinel.utils import get_raster_tile

ZOOM = 14
GEOM_NAME_TEMPLATE = 'Y_{}'
PIXELS_NAME_TEMPLATE = 'X_{}'
NODATA = 0
CATEGORIES_KEY = 'categories'
Y_DTYPE = 'uint8'
Y_DTYPE_CONTINUOUS = 'float32'
SID_DTYPE = 'uint32'


def combine_trainingpixels_patches(trainingpixels_id):
    """
    Choose if trainingpixels collection is 1D or 2D based.
    """
    tp = TrainingPixels.objects.get(id=trainingpixels_id)
    tp.write('Started combining trainingpixel patches.', TrainingPixels.PROCESSING)

    if tp.flatten:
        tp = combine_trainingpixels_patches_flatten(tp)
    else:
        tp = combine_trainingpixels_patches_2d(tp)

    tp.write('Finished pixel collection successfully.', TrainingPixels.FINISHED)


def combine_trainingpixels_patches_2d(tp):
    """
    Combine all trainingpatches into one npz file keeping 2D structure.
    """
    # Prepare data containers.
    all_data = {}
    for patch in tp.trainingpixelspatch_set.all():
        patch_data = numpy.load(patch.collected_pixels)
        for key, val in patch_data.items():
            key_with_id = '{}_{}'.format(key, patch.id)
            all_data[key_with_id] = val
    # Store collected items.
    with TemporaryFile() as fl:
        numpy.savez_compressed(fl, **all_data)
        name = 'trainingpixels-collected-pixels-{}.npz'.format(tp.id)
        tp.collected_pixels.save(name, File(fl))

    return tp


def combine_trainingpixels_patches_flatten(tp):
    """
    Combine all trainingpatches into one npz file where pixels are flattened
    so that 2D structure is lost.
    """
    # Prepare data containers.
    Xs = OrderedDict()
    Ys = OrderedDict()
    categories = {}
    for patch in tp.trainingpixelspatch_set.all():
        patch_data = numpy.load(patch.collected_pixels)
        for key, val in patch_data.items():
            # Process category dict.
            if key == CATEGORIES_KEY:
                categories.update({catkey: int(catval) for catkey, catval in val})
                continue
            # Split key name to determine X vs Y and get the PK of the sample.
            xory, pk = key.split('_')
            pk = int(pk)
            if xory == 'X':
                # We are not (yet) interested in the 2D shape of the sample, so
                # lets ravel things down to the pixel level.
                new_shp = (val.shape[0], val.shape[1], val.shape[2] * val.shape[3])
                val = val.reshape(new_shp)
                val = val.swapaxes(0, 2)
                val = val.swapaxes(1, 2)
                # Drop any pixel that has nodata in any of the timesteps or bands.
                val = val[~numpy.any(val == NODATA, axis=(1, 2))]
                Xs[pk] = val
            else:
                # Only keep the class number by id, the shape of the training
                # will be lost but is not (yet) of interest.
                Ys[pk] = numpy.unique(val[val > 0])
    # Select datatype for Y.
    y_dtype = Y_DTYPE_CONTINUOUS if tp.traininglayer.continuous else Y_DTYPE
    # Construct training pixel level 1D data arrays.
    Ys1D = []
    sample_ids = []
    for pk, val in Xs.items():
        Ys1D.append((numpy.ones(val.shape[0]) * Ys[pk]).astype(y_dtype))
        sample_ids.append((numpy.ones(val.shape[0]) * pk).astype(SID_DTYPE))
    # Stack Xs and Ys.
    X = numpy.vstack(list(Xs.values()))
    Y = numpy.hstack(Ys1D)
    # Pixel IDs.
    PID = numpy.arange(Y.shape[0]) + 1
    # Sample IDs.
    SID = numpy.hstack(sample_ids)
    # Add categories to traininglayer, swapping keys with values because that
    # is how the traininglayer legend should be stored.
    tp.traininglayer.legend = {val: key for key, val in categories.items()}
    tp.traininglayer.save()
    # Convert categories dict to array (to avoid pickling objects).
    categories = numpy.array([numpy.array([key, val]) for key, val in categories.items()])
    # Store collected items.
    with TemporaryFile() as fl:
        numpy.savez_compressed(fl, X=X, Y=Y, PID=PID, SID=SID, categories=categories)
        name = 'trainingpixels-collected-pixels-{}.npz'.format(tp.id)
        tp.collected_pixels.save(name, File(fl))

    return tp


def populate_trainingpixels(trainingpixels_id):
    """
    Create trainingpixel patches and push their collection tasks.
    """
    # Get object.
    tp = TrainingPixels.objects.get(id=trainingpixels_id)
    nr_of_samples = tp.traininglayer.trainingsample_set.all().count()
    counter = 0
    for idx in range(0, nr_of_samples, tp.patch_size):
        TrainingPixelsPatch.objects.get_or_create(
            trainingpixels=tp,
            index_from=idx,
            index_to=min(idx + tp.patch_size, nr_of_samples),
        )
        counter += 1
    tp.write('Pushed {} trainingpixel patch jobs.'.format(counter), TrainingPixels.PROCESSING)
    for patch in tp.trainingpixelspatch_set.all():
        patch.write('Scheduled patch.', TrainingPixelsPatch.PENDING)
        ecs.populate_trainingpixels_patch(patch.id, tp.needs_large_instance)


def populate_trainingpixels_patch(trainingpixelspatch_id):
    """
    Collect pixels for one trainingpixels patch.
    """
    # Get patch instance and log processing status.
    patch = TrainingPixelsPatch.objects.get(id=trainingpixelspatch_id)
    patch.write('Collecting pixels.', TrainingPixelsPatch.PROCESSING)
    # Prepare variables for re-use in loop.
    trainingpixels = patch.trainingpixels
    composites = trainingpixels.composites.all().order_by('min_date')
    band_names = trainingpixels.band_names.split(',')
    # Select datatype for Y.
    y_dtype = Y_DTYPE_CONTINUOUS if trainingpixels.traininglayer.continuous else Y_DTYPE
    # Prepare data containers.
    result = {}
    categories = {}
    for sample in trainingpixels.traininglayer.trainingsample_set.order_by('id').all()[patch.index_from:patch.index_to]:
        # Track categories.
        if not trainingpixels.traininglayer.continuous:
            categories[sample.category] = int(sample.value)
        # Prepare rasterlayer ids.
        rasterlayer_ids_lookups = prepare_sample_lookups(trainingpixels.id, sample, composites, trainingpixels.look_back_steps, band_names)
        # Continue if no match has been found.
        if not rasterlayer_ids_lookups:
            continue
        # Get geometry in web mercator projection.
        geom = sample.geom.transform(3857, clone=True)
        # Compute tile range for this geom.
        geom_buffered = None
        if trainingpixels.buffer:
            # Buffer geom if required.
            geom_buffered = geom.buffer(trainingpixels.buffer)
            idx = tile_index_range(geom_buffered.extent, ZOOM)
        else:
            idx = tile_index_range(geom.extent, ZOOM)
        # Rasterize geom and set pixel values to class value.
        geom_pixels = get_pixels(idx, geom, trainingpixels.training_all_touched).astype(y_dtype)
        # Compute clipping mask.
        if trainingpixels.buffer:
            geom_buffered_pixels = get_pixels(idx, geom_buffered, trainingpixels.training_all_touched).astype(y_dtype)
            geom_mask = geom_buffered_pixels == 0
        else:
            geom_mask = geom_pixels == 0
        # Set Y geom pixels to sample value.
        geom_pixels = (sample.value * geom_pixels).astype(y_dtype)
        # Store Y pixels.
        result[GEOM_NAME_TEMPLATE.format(sample.id)] = geom_pixels
        # Get pixels.
        patch_result = []
        ignore_sample = False
        for rasterlayer_ids in rasterlayer_ids_lookups:
            if ignore_sample:
                break
            composite_pixels = []
            for rasterlayer_id in rasterlayer_ids:
                band_pixels = get_pixels(idx, rasterlayer_id)
                if band_pixels is None:
                    ignore_sample = True
                    break
                # Clip band to geometry to reduce compressed data size.
                band_pixels[geom_mask] = NODATA
                composite_pixels.append(band_pixels)
            patch_result.append(numpy.array(composite_pixels))
        # Add this sample pixel stack to result dictionary, if there was data
        # for this sample.
        if not ignore_sample:
            result[PIXELS_NAME_TEMPLATE.format(sample.id)] = numpy.array(patch_result)
    # Track categories present.
    if not trainingpixels.traininglayer.continuous:
        result[CATEGORIES_KEY] = numpy.array([numpy.array([key, val]) for key, val in categories.items()])
    # Store collected pixels.
    patch.write('Successfully collected pixels, storing result.', TrainingPixelsPatch.PROCESSING)
    with TemporaryFile() as fl:
        numpy.savez_compressed(fl, **result)
        name = 'trainingpixelspatch-collected-pixels-{}.npz'.format(patch.id)
        patch.collected_pixels.save(name, File(fl))
    patch.write('Successfully collected pixels, storing result.', TrainingPixelsPatch.FINISHED)
    # Push combination of patches into one file when all patches are done.
    if not TrainingPixelsPatch.objects.filter(trainingpixels_id=patch.trainingpixels_id).exclude(status=TrainingPixelsPatch.FINISHED).exists():
        patch.trainingpixels.write('Finished collecting all patches, scheduled combining them into one.', TrainingPixels.PENDING)
        ecs.combine_trainingpixels_patches(patch.trainingpixels_id)


def get_pixels(idx, src, all_touched=None):
    """
    Collect pixels over an index range and either a rasterlayer ID or as a
    rasterized geometry.
    """
    hstack = []
    for tilex in range(idx[0], idx[2] + 1):
        vstack = []
        for tiley in range(idx[1], idx[3] + 1):
            if isinstance(src, int):
                tile = get_raster_tile(src, ZOOM, tilex, tiley)
                # Abort pixel collection if tile could not be found.
                if not tile:
                    return
                vstack.append(tile.bands[0].data())
            else:
                vstack.append(rasterize_geom(src, ZOOM, tilex, tiley, all_touched))
        hstack.append(numpy.vstack(vstack))
    return numpy.hstack(hstack)


def prepare_sample_lookups(trainingpixels_id, sample, composites, look_back_steps, band_names):
    """
    Extract rasterlayer ids for all composites and all bands requested in the
    collection task.
    """
    # Check if all composites should be included in training (fixed end
    # date for all samples) or a flexible selection shall be used based on
    # the sample date stamp.
    if look_back_steps > 0:
        # Get first composite after the min date.
        try:
            composite_after = composites.filter(min_date__gte=sample.date)[0]
        except IndexError:
            trainingpixels = TrainingPixels.objects.get(pk=trainingpixels_id)
            trainingpixels.write('Skipping sample {}. No composites could be found after sample date {}.'.format(sample.id, sample.date))
            return
        # Select the last N steps before the.
        if look_back_steps > 1:
            composites_before = composites.order_by('-min_date').exclude(min_date__gte=sample.date)[:(look_back_steps - 1)]
            if len(composites_before) != look_back_steps - 1:
                msg = 'Skipping sample {}. Failed finding {} composites before sample date {}, only found {}.'.format(
                    sample.id,
                    look_back_steps - 1,
                    sample.date,
                    len(composites_before),
                )
                trainingpixels = TrainingPixels.objects.get(pk=trainingpixels_id)
                trainingpixels.write(msg)
                return
            composites_before = reversed(list(composites_before))
        else:
            composites_before = []
        # Combine the "last after date" and "N before date" composite lists.
        sample_composites = list(composites_before) + [composite_after]
    else:
        # Select all available composites.
        sample_composites = composites

    return [get_rasterlayer_ids(band_names, composite.rasterlayer_lookup) for composite in sample_composites]


def rasterize_geom(geom, tilez, tilex, tiley, all_touched):
    """
    Rasterize a geometry over a tile.
    """
    # Create a target raster for the rasterization.
    bounds = tile_bounds(tilex, tiley, tilez)
    rast = GDALRaster(
        {
            'width': WEB_MERCATOR_TILESIZE,
            'height': WEB_MERCATOR_TILESIZE,
            'srid': WEB_MERCATOR_SRID,
            'scale': [SCALE, -SCALE],
            'origin': [bounds[0], bounds[3]],
            'datatype': 1,
            'nr_of_bands': 1,
        }
    )
    # Rasterize the sample area.
    sample_rast = rasterize(geom, rast, all_touched=all_touched)
    return sample_rast.bands[0].data()
