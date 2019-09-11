from rest_framework.serializers import CharField, FloatField, SerializerMethodField

from raster_api.serializers import PermissionsModelSerializer
from report.models import ReportAggregation, ReportSchedule


class ReportScheduleSerializer(PermissionsModelSerializer):

    class Meta:
        model = ReportSchedule
        fields = (
            'id', 'aggregationlayer', 'formula', 'composite', 'predictedlayer',
        )


class ReportAggregationSerializer(PermissionsModelSerializer):

    value = SerializerMethodField()
    status = CharField(source='valuecountresult.status')
    min = FloatField(source='valuecountresult.stats_min')
    max = FloatField(source='valuecountresult.stats_max')
    avg = FloatField(source='valuecountresult.stats_avg')
    std = FloatField(source='valuecountresult.stats_std')
    pcount = FloatField(source='valuecountresult.stats_cumsum_t0')
    psum = FloatField(source='valuecountresult.stats_cumsum_t1')
    psumsq = FloatField(source='valuecountresult.stats_cumsum_t2')

    class Meta:
        model = ReportAggregation
        fields = (
            'id', 'formula', 'aggregationlayer', 'aggregationarea', 'composite',
            'predictedlayer', 'valuecountresult',
            'value', 'status', 'min', 'max', 'avg', 'std', 'pcount', 'psum', 'psumsq',

        )

    def get_value(self, obj):
        """
        Convert keys to strings and hstore values to floats.
        """
        return {str(k): float(v) for k, v in obj.valuecountresult.value.items()}
