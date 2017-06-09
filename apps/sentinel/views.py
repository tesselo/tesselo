from django_filters.rest_framework import DjangoFilterBackend
from PIL import Image
from raster.tiles.utils import get_raster_tile
from raster.views import RasterView
from rest_framework import viewsets

import numpy
from django.http import Http404
from django.shortcuts import get_object_or_404
from sentinel.clouds.tables import clouds
from sentinel.models import SentinelTile, WorldLayerGroup
from sentinel.serializers import WorldLayerGroupSerializer


class WorldLayerGroupViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = WorldLayerGroup.objects.all()
    serializer_class = WorldLayerGroupSerializer
    filter_backends = (DjangoFilterBackend, )
    filter_fields = ('active', )


class CloudView(RasterView):

    def get(self, request, stile, z, x, y, **kwargs):

        scene = get_object_or_404(SentinelTile, pk=stile)

        stack = {}
        for band in scene.sentineltileband_set.all():
            tile = get_raster_tile(
                layer_id=band.layer_id,
                tilez=int(z),
                tilex=int(x),
                tiley=int(y),
            )
            if not tile:
                raise Http404('Tile not found.')
            stack[band.band] = tile.bands[0].data()

        # Compute cloud confidence mask.
        cloud_probs = clouds(stack)

        # Reshape and rescale probabilities to png value range.
        size = 256 * 256
        cloud_probs = cloud_probs.flatten() * 255
        cloud_probs = cloud_probs.repeat(3).reshape((size, 3))

        # Create array of ones for alpha channel.
        alpha = numpy.ones((size, 1)) * 255

        # Create rgba matrix.
        rgba = numpy.append(cloud_probs, alpha, axis=1)

        # Reshape array to image size
        rgba = rgba.reshape(256, 256, 4)

        # Create image from array
        img = Image.fromarray(rgba.astype('uint8'))

        return self.write_img_to_response(img, {})
