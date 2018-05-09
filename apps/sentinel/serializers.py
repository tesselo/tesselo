from rest_framework.serializers import ModelSerializer

from sentinel.models import CompositeBuild, CompositeTile, SentinelTile


class SentinelTileSerializer(ModelSerializer):

    class Meta:
        model = SentinelTile
        fields = (
            'id', 'prefix', 'rasterlayer_lookup', 'collected', 'cloudy_pixel_percentage',
            'data_coverage_percentage', 'angle_azimuth', 'angle_altitude',
        )


class CompositeBuildSerializer(ModelSerializer):

    class Meta:
        model = CompositeBuild
        fields = (
            'id', 'composite', 'aggregationlayer', 'log', 'status',
            'owner', 'sentineltiles', 'compositetiles',
        )
        read_only_fields = ('sentineltiles', 'compositetiles', )


class CompositeTileSerializer(ModelSerializer):

    class Meta:
        model = CompositeTile
        fields = (
            'id', 'composite', 'status', 'tilez', 'tilex', 'tiley', 'scheduled',
            'start', 'end', 'log',
        )
