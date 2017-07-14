{% extends "gis/admin/openlayers.js" %}

{% block map_creation %}
    {{ module }}.map = new OpenLayers.Map('{{ id }}_map', options);
    // Base Layer
    {{ module }}.layers.base = {% block base_layer %}new OpenLayers.Layer.OSM("OSM");{% endblock %}
    {{ module }}.map.addLayer({{ module }}.layers.base);
    // Satellite layer.
    {% if tileurl %}
        {{ module }}.layers.satellite = new OpenLayers.Layer.XYZ('Satellite', '{{ tileurl }}', {isBaseLayer: false});
        {{ module }}.map.addLayer({{ module }}.layers.satellite);
    {% endif %}
{% endblock %}
