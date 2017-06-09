from rest_framework import serializers

from sentinel.models import WorldLayerGroup


class WorldLayerGroupSerializer(serializers.ModelSerializer):

    class Meta:
        model = WorldLayerGroup
        fields = ('id', 'name', 'kahunas')
