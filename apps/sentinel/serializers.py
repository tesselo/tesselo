from rest_framework.serializers import ModelSerializer

from sentinel.models import SentinelTile


class SentinelTileSerializer(ModelSerializer):

    class Meta:
        model = SentinelTile
        fields = (
            'id', 'prefix', 'rasterlayer_lookup', 'collected', 'cloudy_pixel_percentage',
            'data_coverage_percentage', 'angle_azimuth', 'angle_altitude',
        )
