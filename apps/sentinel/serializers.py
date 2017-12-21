from rest_framework.serializers import ModelSerializer

from sentinel.models import SentinelTile, WorldLayerGroup


class SentinelTileSerializer(ModelSerializer):

    class Meta:
        model = SentinelTile
        fields = (
            'id', 'prefix', 'kahunas', 'collected', 'cloudy_pixel_percentage',
            'data_coverage_percentage', 'angle_azimuth', 'angle_altitude'
        )


class WorldLayerGroupSerializer(ModelSerializer):

    class Meta:
        model = WorldLayerGroup
        fields = ('id', 'name', 'kahunas')
