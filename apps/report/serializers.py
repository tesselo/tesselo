import json

from rest_framework.serializers import CharField, FloatField, SerializerMethodField

from raster_api.serializers import PermissionsModelSerializer
from report.models import ReportAggregation, ReportSchedule


class ReportScheduleSerializer(PermissionsModelSerializer):

    class Meta:
        model = ReportSchedule
        fields = (
            'id', 'aggregationlayers', 'formulas', 'composites',
            'predictedlayers', 'active',
        )


class ReportAggregationSerializer(PermissionsModelSerializer):

    value = SerializerMethodField()
    name = CharField(source='aggregationarea.name')
    geom = SerializerMethodField()
    min = FloatField(source='stats_min')
    max = FloatField(source='stats_max')
    avg = FloatField(source='stats_avg')
    std = FloatField(source='stats_std')
    pcount = FloatField(source='stats_cumsum_t0')
    psum = FloatField(source='stats_cumsum_t1')
    psumsq = FloatField(source='stats_cumsum_t2')

    class Meta:
        model = ReportAggregation
        fields = (
            'id', 'formula', 'aggregationlayer', 'aggregationarea', 'composite',
            'predictedlayer', 'name', 'geom', 'min_date', 'max_date', 'value',
            'min', 'max', 'avg', 'std', 'pcount', 'psum', 'psumsq',
        )

    def get_value(self, obj):
        """
        Convert keys to strings and hstore values to floats.
        """
        return {str(k): float(v) for k, v in obj.value.items()}

    def get_geom(self, obj):
        """
        Name of aggregation area.
        """
        return json.loads(obj.aggregationarea.geom.transform(4326, clone=True).geojson)
