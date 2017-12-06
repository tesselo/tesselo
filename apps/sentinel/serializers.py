from rest_framework.serializers import ModelSerializer, SerializerMethodField

from sentinel.models import SentinelTile, WorldLayerGroup


class SentinelTileSerializer(ModelSerializer):

    kahunas = SerializerMethodField()

    class Meta:
        model = SentinelTile
        fields = (
            'id', 'prefix', 'kahunas', 'collected', 'cloudy_pixel_percentage',
            'data_coverage_percentage', 'angle_azimuth', 'angle_altitude'
        )

    def get_kahunas(self, obj):
        return {band.band: band.layer_id for band in obj.sentineltileband_set.all()}


class WorldLayerGroupSerializer(ModelSerializer):

    class Meta:
        model = WorldLayerGroup
        fields = ('id', 'name', 'kahunas')
