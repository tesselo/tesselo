from formulary.models import Formula
from raster_api.serializers import PermissionsModelSerializer


class FormulaSerializer(PermissionsModelSerializer):

    class Meta:
        model = Formula
        fields = (
            'id', 'name', 'acronym', 'description', 'formula', 'min_val', 'max_val', 'breaks',
            'color_palette',
        )
