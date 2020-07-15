import json
from collections import Counter
from math import ceil

import numpy
import rasterio
from raster.algebra.parser import FormulaParser, RasterAlgebraParser
from raster.exceptions import RasterAggregationException
from raster.models import Legend
from raster.tiles.const import WEB_MERCATOR_SRID
from raster.valuecount import Aggregator
from rasterio import Affine
from rasterio.crs import CRS
from rasterio.features import bounds, rasterize
from rasterio.io import MemoryFile
from rasterio.warp import Resampling, calculate_default_transform, reproject

from report.const import ALLOWED_LINEAR_UNITS
from sentinel.utils import get_raster_tile

VALUECOUNT_ROUNDING_DIGITS = 7


class AggregatorProjectionSimple(Aggregator):

    def __init__(self, *args, **kwargs):
        # Get srid argument.
        self.srid = kwargs.pop('srid', WEB_MERCATOR_SRID)
        # Initiate class.
        super().__init__(*args, **kwargs)

    def get_raster_tile(self, layerid, zoom, tilex, tiley):
        """
        A patched aggregator function, using the direct S3 tile lookup approach.
        This reduces load on DB dramatically.
        """
        return get_raster_tile(layerid, zoom, tilex, tiley)


class AggregatorProjection(AggregatorProjectionSimple):

    def __init__(self, *args, **kwargs):
        # Get srid argument.
        self.srid = kwargs.pop('srid', WEB_MERCATOR_SRID)
        # Initiate class.
        super().__init__(*args, **kwargs)
        # Project geom into requested srid.
        self.geom = self.geom.transform(self.srid, clone=True)

    def get_raster_tile(self, layerid, zoom, tilex, tiley):
        """
        A patched aggregator function, using the direct S3 tile lookup approach.
        This reduces load on DB dramatically.
        """
        return get_raster_tile(layerid, zoom, tilex, tiley)

    def tiles(self):
        """
        Generator that yields an algebra-ready data dictionary for each tile in
        the aggregator's tile range. The result is returned as rasterio memfile
        objects.
        """
        # Check if any tiles have been matched
        if not self.tilerange:
            return
        algebra_parser = RasterAlgebraParser()
        for tilex in range(self.tilerange[0], self.tilerange[2] + 1):
            for tiley in range(self.tilerange[1], self.tilerange[3] + 1):
                # Prepare a data dictionary with named tiles for algebra evaluation
                data = {}
                for name, layerid in self.layer_dict.items():
                    tile = self.get_raster_tile(layerid, self.zoom, tilex, tiley)
                    if tile:
                        data[name] = tile
                    else:
                        break

                # Ignore this tile if it is missing in any of the input layers
                if len(data) < len(self.layer_dict):
                    continue

                # Compute raster algebra
                result = algebra_parser.evaluate_raster_algebra(data, self.formula)

                # Convert to uint8 if discrete.
                yield tilex, tiley, result

    def value_count(self):
        # Instantiate counter dict for value counts.
        results = Counter({})
        self._clear_stats()

        # Set the destination crs to the one from the input geometry.
        dst_crs = CRS.from_epsg(self.geom.srid)

        # Perform a sanity check on target crs.
        if dst_crs.linear_units.lower() not in ALLOWED_LINEAR_UNITS:
            raise RasterAggregationException('Units of dst crs need to be in meters, found {}.'.format(dst_crs.linear_units))

        # Combine all tiles into one big array.
        row_length = 1 + (self.tilerange[3] - self.tilerange[1])
        row = []
        for tilex, tiley, rst in self.tiles():
            # Prepare affine transform to create rasterio raster.
            if len(row) == 0:
                transform = Affine(rst.scale.x, rst.skew.x, rst.origin.x, rst.skew.y, rst.scale.y, rst.origin.y)
            # Get first band.
            band = rst.bands[0]
            # Add this tile to the row.
            row.append(band.data())
            # Handle end of row.
            if len(row) == row_length:
                # Stack row.
                row = numpy.hstack(row)
                # Prepare the creation args for the new rasterio raster.
                creation_args = {
                    'driver': 'GTiff',
                    'dtype': band.datatype(as_string=True).split('GDT_')[1].lower(),
                    'nodata': band.nodata_value,
                    'width': row.shape[1],
                    'height': row.shape[0],
                    'count': 1,
                    'crs': 'EPSG:{}'.format(rst.srid),
                    'transform': transform,
                }
                # Warp raster data and clip to geometry.
                self.pixel_size_m2, result_data = warp_and_clip(creation_args, row, self.geom)

                # For the resulting array, compute the statistics.
                if self.grouping == 'discrete':
                    # Compute unique counts for discrete input data
                    unique_counts = numpy.unique(result_data, return_counts=True)
                    # Add counts to results
                    values = dict(zip(unique_counts[0], unique_counts[1]))

                elif self.grouping == 'continuous':
                    if self.memory_efficient and not self.hist_range:
                        raise RasterAggregationException(
                            'Secify a histogram range for memory efficient continuous aggregation.'
                        )

                    # Handle continuous case - compute histogram on masked data
                    counts, bins = numpy.histogram(result_data, range=self.hist_range)

                    # Create dictionary with bins as keys and histogram counts as values
                    values = {}
                    for i in range(len(bins) - 1):
                        values[(bins[i], bins[i + 1])] = counts[i]

                else:
                    # If input is not a legend, interpret input as legend json data
                    if not isinstance(self.grouping, Legend):
                        self.grouping = Legend(json=self.grouping)

                    # Try getting a colormap from the input
                    try:
                        colormap = self.grouping.colormap
                    except:
                        raise RasterAggregationException(
                            'Invalid grouping value found for valuecount.'
                        )

                    # Use colormap to compute value counts
                    formula_parser = FormulaParser()
                    values = {}
                    for key, color in colormap.items():
                        try:
                            # Try to use the key as number directly
                            selector = result_data == float(key)
                        except ValueError:
                            # Otherwise use it as numpy expression directly
                            selector = formula_parser.evaluate({'x': result_data}, key)
                        values[key] = numpy.sum(selector)

                # Add counts to results.
                results.update(Counter(values))
                # Push statistics.
                self._push_stats(result_data)
                # Reset the row.
                row = []

        # Transform pixel count to hectares.
        scaling_factor = 1
        if len(results):
            scaling_factor = self.pixel_size_m2 / 10000

        results = {
            str(int(k) if type(k) == numpy.float64 and int(k) == k else k):
            v * scaling_factor for k, v in results.items()
        }

        return results

    def value_count_old(self):
        """
        Patched version of the original value_count from the aggregation package.

        This allows for the input geometries to be in a different projection
        and the statistics are computed in the geom's projection, not the
        web mercator one.
        """
        # Instantiate counter dict for value counts.
        results = Counter({})
        self._clear_stats()

        # Set the destination crs to the one from the input geometry.
        dst_crs = CRS.from_epsg(self.geom.srid)

        # Perform a sanity check on target crs.
        if dst_crs.linear_units.lower() not in ALLOWED_LINEAR_UNITS:
            raise RasterAggregationException('Units of dst crs need to be in meters, found {}.'.format(dst_crs.linear_units))

        # Combine all tiles into one big array.
        for creation_args, band_data in self.tiles():
            with MemoryFile() as memfile_src:
                with memfile_src.open(**creation_args) as src:
                    src.write(band_data, 1)
                    # Compute transformation for destination file.
                    dst_transform, width, height = calculate_default_transform(
                        src.crs,
                        dst_crs,
                        src.width,
                        src.height,
                        *src.bounds,
                    )
                    # Create destination args.
                    dst_creation_args = src.meta.copy()
                    dst_creation_args.update({
                        'crs': dst_crs,
                        'transform': dst_transform,
                        'width': width,
                        'height': height,
                    })
                    # Creat destination file.
                    with MemoryFile() as memfile_dst:
                        with memfile_dst.open(**dst_creation_args) as dst:
                            # Reproject each band into the destination raster.
                            reproject(
                                source=rasterio.band(src, 1),
                                destination=rasterio.band(dst, 1),
                                src_transform=src.transform,
                                src_crs=src.crs,
                                dst_transform=dst_transform,
                                dst_crs=dst_crs,
                                resampling=Resampling.nearest,
                            )
                            # Compute size in m2 of the pixels in the image.
                            pixel_size_m2 = abs(dst.transform[0] * dst.transform[4])
                            # Rasterize the geometry and use the mask on all bands.
                            geom_rasterized = rasterize(
                                [json.loads(self.geom.geojson)],
                                out_shape=(dst.height, dst.width),
                                fill=dst.nodata,
                                transform=dst.transform,
                                all_touched=False,
                                default_value=1,
                                dtype='uint8',
                            )
                            # Convert the rasterized geometry into a boolean array.
                            geom_rasterized = geom_rasterized == 1
                            # Mask the destination raster using the rasterized geometry.
                            result_data = dst.read(1)[geom_rasterized].ravel()

                            # For the resulting array, compute the statistics.
                            if self.grouping == 'discrete':
                                # Compute unique counts for discrete input data
                                unique_counts = numpy.unique(result_data, return_counts=True)
                                # Add counts to results
                                values = dict(zip(unique_counts[0], unique_counts[1]))

                            elif self.grouping == 'continuous':
                                if self.memory_efficient and not self.hist_range:
                                    raise RasterAggregationException(
                                        'Secify a histogram range for memory efficient continuous aggregation.'
                                    )

                                # Handle continuous case - compute histogram on masked data
                                counts, bins = numpy.histogram(result_data, range=self.hist_range)

                                # Create dictionary with bins as keys and histogram counts as values
                                values = {}
                                for i in range(len(bins) - 1):
                                    values[(bins[i], bins[i + 1])] = counts[i]

                            else:
                                # If input is not a legend, interpret input as legend json data
                                if not isinstance(self.grouping, Legend):
                                    self.grouping = Legend(json=self.grouping)

                                # Try getting a colormap from the input
                                try:
                                    colormap = self.grouping.colormap
                                except:
                                    raise RasterAggregationException(
                                        'Invalid grouping value found for valuecount.'
                                    )

                                # Use colormap to compute value counts
                                formula_parser = FormulaParser()
                                values = {}
                                for key, color in colormap.items():
                                    try:
                                        # Try to use the key as number directly
                                        selector = result_data == float(key)
                                    except ValueError:
                                        # Otherwise use it as numpy expression directly
                                        selector = formula_parser.evaluate({'x': result_data}, key)
                                    values[key] = numpy.sum(selector)

                            # Add counts to results.
                            results.update(Counter(values))
                            # Push statistics.
                            self._push_stats(result_data)

        # Transform pixel count to hectares.
        scaling_factor = 1
        if len(results):
            scaling_factor = pixel_size_m2 / 10000

        results = {
            str(int(k) if type(k) == numpy.float64 and int(k) == k else k):
            v * scaling_factor for k, v in results.items()
        }

        return results

    def _push_stats(self, data):
        # Stop if entire data was masked
        if data.size == 0:
            return

        # Filter data by histogram range.
        if self.hist_range:
            stats_data = data[data >= self.hist_range[0]]
            stats_data = stats_data[stats_data <= self.hist_range[1]]
        else:
            stats_data = data

        # Return early if the hist range filter reduced the data to nothing.
        if stats_data.size == 0:
            return

        # Compute incremental statistics
        self._stats_t0 += stats_data.size
        self._stats_t1 += numpy.sum(stats_data)
        self._stats_t2 += numpy.sum(numpy.square(stats_data))

        tile_max = numpy.max(stats_data)
        tile_min = numpy.min(stats_data)

        if self._stats_max_value is None:
            self._stats_max_value = tile_max
            self._stats_min_value = tile_min
        else:
            self._stats_max_value = max(tile_max, self._stats_max_value)
            self._stats_min_value = min(tile_min, self._stats_min_value)

    def statistics(self, reset=False):
        """
        Compute statistics for this aggregator. Returns (min, max, mean, std).
        The mean and std can be computed incrementally from the number of
        obeservations t0 = sum(x^0), the sum of values t1 = sum(x^1), and the
        sum of squares t2 = sum(x^2).
        """
        if self._stats_t0 == 0:
            # If totals sum is zero, no data was available to comput statistics
            mean = None
            std = None
        else:
            # Compute mean and std from totals sums.
            mean = self._stats_t1 / self._stats_t0
            std = numpy.sqrt(self._stats_t0 * self._stats_t2 - self._stats_t1 * self._stats_t1) / self._stats_t0

        return (self._stats_min_value, self._stats_max_value, mean, std)


def populate_vc(vc, srid):
    # Compute range for valuecounts if provided.
    if vc.range_min is not None and vc.range_max is not None:
        hist_range = (vc.range_min, vc.range_max)
    else:
        hist_range = None

    try:
        # Compute aggregate result.
        agg = AggregatorProjection(
            layer_dict=vc.layer_names,
            formula=vc.formula,
            zoom=vc.zoom,
            geom=vc.aggregationarea.geom,
            acres=vc.units.lower() == 'acres',
            grouping=vc.grouping,
            hist_range=hist_range,
            srid=srid,
        )
        aggregation_result = agg.value_count()
        vc.stats_min, vc.stats_max, vc.stats_avg, vc.stats_std = agg.statistics()

        # Track cumulative data to be able to generalize stats over
        # multiple aggregation areas.
        vc.stats_cumsum_t0 = agg._stats_t0
        vc.stats_cumsum_t1 = agg._stats_t1
        vc.stats_cumsum_t2 = agg._stats_t2

        # Make a copy of the pixel size.
        vc.pixel_size_m2 = agg.pixel_size_m2

        # Convert values to string for storage in hstore.
        vc.value = {k: str(round(v, VALUECOUNT_ROUNDING_DIGITS)) for k, v in aggregation_result.items()}

        vc.status = vc.FINISHED
    except:
        vc.status = vc.FAILED

    vc.save()

    return vc


def compute_transform(geom, scale):
    """
    Compute warp parameters from geometry. The scale is expected to be in the
    coordinate system units of the geometry.
    """
    extent = bounds(geom)
    transform = Affine(scale, 0, extent[0], 0, -scale, extent[3])
    width = ceil((extent[2] - extent[0]) / scale)
    height = ceil((extent[3] - extent[1]) / scale)

    return transform, width, height


def gdalraster_to_rasterio(rst):
    """
    Convert a GDALRaster object to a rasterio memoryfile dataset.
    """
    # Get list of bands.
    bands = [band for band in rst.bands]
    if len(bands) != 1:
        raise RasterAggregationException('For aggregation, band count needs to be exactly 1.')
    band = bands[0]
    # Prepare affine transform to create rasterio raster.
    transform = Affine(rst.scale.x, rst.skew.x, rst.origin.x, rst.skew.y, rst.scale.y, rst.origin.y)
    # Prepare the creation args for the new rasterio raster.
    creation_args = {
        'driver': 'GTiff',
        'dtype': band.datatype(as_string=True).split('GDT_')[1].lower(),
        'nodata': band.nodata_value,
        'width': rst.width,
        'height': rst.height,
        'count': 1,
        'crs': 'EPSG:{}'.format(rst.srid),
        'transform': transform,
    }
    # Create memfile and copy pixel values from GDALRaster to rasterio file.
    return creation_args, band.data()


def warp_and_clip(creation_args, data, geom):
    """
    Warp a data matrix into new creation args, and clip against the geometry.
    """
    # Set the destination crs to the one from the input geometry.
    dst_crs = CRS.from_epsg(geom.srid)
    # Create memfile with data.
    with MemoryFile() as memfile_src:
        with memfile_src.open(**creation_args) as src:
            src.write(data, 1)
            # Compute transformation for destination file.
            dst_transform, width, height = calculate_default_transform(
                src.crs,
                dst_crs,
                src.width,
                src.height,
                *src.bounds,
            )
            # Create destination args.
            dst_creation_args = src.meta.copy()
            dst_creation_args.update({
                'crs': dst_crs,
                'transform': dst_transform,
                'width': width,
                'height': height,
            })
            # Creat destination file.
            with MemoryFile() as memfile_dst:
                with memfile_dst.open(**dst_creation_args) as dst:
                    # Reproject each band into the destination raster.
                    reproject(
                        source=rasterio.band(src, 1),
                        destination=rasterio.band(dst, 1),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=dst_transform,
                        dst_crs=dst_crs,
                        resampling=Resampling.nearest,
                    )
                    # Compute size in m2 of the pixels in the image.
                    pixel_size_m2 = abs(dst.transform[0] * dst.transform[4])
                    # Rasterize the geometry and use the mask on all bands.
                    geom_rasterized = rasterize(
                        [json.loads(geom.geojson)],
                        out_shape=(dst.width, dst.height),
                        fill=dst.nodata,
                        transform=dst.transform,
                        all_touched=False,
                        default_value=1,
                        dtype='uint8',
                    )
                    # Convert the rasterized geometry into a boolean array.
                    geom_rasterized = geom_rasterized == 1
                    # Mask the destination raster using the rasterized geometry.
                    return pixel_size_m2, dst.read(1)[geom_rasterized.T].ravel()
