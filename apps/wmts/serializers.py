from raster_api.serializers import PermissionsModelSerializer
from wmts.models import WMTSLayer


class WMTSLayerSerializer(PermissionsModelSerializer):

    class Meta:
        model = WMTSLayer
        fields = (
            'id', 'title', 'formula', 'sentineltile', 'composite',
        )
