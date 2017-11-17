from guardian.shortcuts import get_objects_for_user
from raster.tiles.utils import tile_bounds, tile_scale
from rest_framework.views import APIView

from django.http import HttpResponse


WMTS_BASE_TEMPLATE = '''<?xml version="1.0" encoding="UTF-8"?>
<Capabilities xmlns="http://www.opengis.net/wmts/1.0" xmlns:ows="http://www.opengis.net/ows/1.1" xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:gml="http://www.opengis.net/gml" xsi:schemaLocation="http://www.opengis.net/wmts/1.0 http://schemas.opengis.net/wmts/1.0/wmtsGetCapabilities_response.xsd" version="1.0.0">
        <ows:ServiceIdentification>
                <ows:Title>Web Map Tile Service</ows:Title>
                <ows:ServiceType>OGC WMTS</ows:ServiceType>
                <ows:ServiceTypeVersion>1.0.0</ows:ServiceTypeVersion>
        </ows:ServiceIdentification>
        <ows:ServiceProvider>
                <ows:ProviderName>Tesselo</ows:ProviderName>
                <ows:ProviderSite xlink:href="https://tesselo.com"/>
        </ows:ServiceProvider>
        <Contents>
        {layers}
        {mat}
        </Contents>
        <ServiceMetadataURL xlink:href="https://tesselo.com/wmts"/>
</Capabilities>
'''

TILE_MATRIX_SET_TEMPLATE = '''
<TileMatrixSet>
<ows:Identifier>epsg3857</ows:Identifier>
<ows:BoundingBox crs="urn:ogc:def:crs:EPSG:6.18.3:3857">
<ows:LowerCorner>-20037508.342789244 -20037508.342789244</ows:LowerCorner>
<ows:UpperCorner>20037508.342789244 20037508.342789244</ows:UpperCorner>
</ows:BoundingBox>
<ows:SupportedCRS>urn:ogc:def:crs:EPSG:6.18.3:3857</ows:SupportedCRS>
<WellKnownScaleSet>urn:ogc:def:wkss:OGC:1.0:GoogleMapsCompatible</WellKnownScaleSet>
{content}
</TileMatrixSet>
'''

TILE_MATRIX_TEMPLATE = '''
<TileMatrix>
    <ows:Identifier>{zoom}</ows:Identifier>
    <ScaleDenominator>{denominator}</ScaleDenominator>
    <TopLeftCorner>{tlcx} {tlcy}</TopLeftCorner>
    <TileWidth>256</TileWidth>
    <TileHeight>256</TileHeight>
    <MatrixWidth>{nrtiles}</MatrixWidth>
    <MatrixHeight>{nrtiles}</MatrixHeight>
</TileMatrix>
'''

TILE_LAYER_TEMPLATE = '''
<Layer>
    <ows:Title>{title}</ows:Title>
    <ows:WGS84BoundingBox crs="urn:ogc:def:crs:OGC:2:84">
        <ows:LowerCorner>-180 -90</ows:LowerCorner>
        <ows:UpperCorner>180 90</ows:UpperCorner>
    </ows:WGS84BoundingBox>
    <ows:Identifier>{identifier}</ows:Identifier>
    <Style isDefault="true">
            <ows:Identifier>Default</ows:Identifier>
    </Style>
    <Format>image/png</Format>
    <TileMatrixSetLink>
        <TileMatrixSet>epsg3857</TileMatrixSet>
    </TileMatrixSetLink>
    <ResourceURL format="image/png" template="{url}" resourceType="tile"/>
</Layer>
'''


class WMTSAPIView(APIView):
    """
    WMTS GetCapabilities view.

    Response template from http://maps.wien.gv.at/wmts/1.0.0/WMTSCapabilities.xml
    """

    def get(self, request):
        # Get url base from request.
        host = request.get_host()
        urlbase = '{0}://{1}/api/algebra/'.format(
            'http' if host == 'localhost' else 'https',
            host,
        )

        # Get wmts layers for the request user.
        wmts_layers = get_objects_for_user(request.user, 'formulary.change_wmtslayer')

        # Construct wmts layer list from wmts layers.
        layer_list = ''
        for layer in wmts_layers:
            if layer.formula:
                # Generate raster algebra url.
                url = "{urlbase}{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png?layers={layers}&amp;formula={formula}&amp;colormap={colormap}".format(
                    urlbase=urlbase,
                    layers=layer.layer_ids,
                    formula=layer.formula.formula,
                    colormap=layer.formula.colormap,
                )
            else:
                # Generate RGB url.
                url = "{urlbase}{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png?layers=r={red},g={green},b={blue}&amp;scale=3,3e3&amp;alpha".format(
                    urlbase=urlbase,
                    red=layer.sentineltile.sentineltileband_set.get(band='B04.jp2').layer_id,
                    green=layer.sentineltile.sentineltileband_set.get(band='B03.jp2').layer_id,
                    blue=layer.sentineltile.sentineltileband_set.get(band='B02.jp2').layer_id,
                )

            # Add layer to wmts capabilities list.
            layer_list += TILE_LAYER_TEMPLATE.format(
                title=layer.title,
                identifier='{0}'.format(layer.id),
                url=url
            )

        return HttpResponse(WMTS_BASE_TEMPLATE.format(layers=layer_list, mat=self.tile_matrix_set_3857), content_type="text/xml")

    @property
    def tile_matrix_set_3857(self):
        content = ''

        tlcx = tile_bounds(0, 0, 0)[1]
        tlcy = tile_bounds(0, 0, 0)[3]

        for zoom in range(20):
            content += TILE_MATRIX_TEMPLATE.format(
                zoom=zoom,
                denominator=tile_scale(zoom) / 0.28e-3,
                tlcx=tlcx,
                tlcy=tlcy,
                nrtiles=2 ** zoom,
            )

        return TILE_MATRIX_SET_TEMPLATE.format(content=content)
