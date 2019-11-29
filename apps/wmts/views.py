from guardian.shortcuts import get_objects_for_user
from raster.tiles.utils import tile_bounds, tile_scale
from rest_framework.authentication import BasicAuthentication, SessionAuthentication
from rest_framework.views import APIView

from django.http import HttpResponse
from raster_api.authentication import ExpiringTokenAuthentication, QueryKeyAuthentication
from raster_api.const import GET_QUERY_PARAMETER_AUTH_KEY
from raster_api.views import PermissionsModelViewSet
from wmts.models import WMTSLayer
from wmts.serializers import WMTSLayerSerializer

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
        <ServiceMetadataURL xlink:href="https://tesselo.com/api/wmts/"/>
</Capabilities>
'''.strip()

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
'''.strip()

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
'''.strip()

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
'''.strip()


class WMTSAPIView(APIView):
    """
    WMTS GetCapabilities view.

    Response template from http://maps.wien.gv.at/wmts/1.0.0/WMTSCapabilities.xml
    """
    # Putting the basic authentication first, so that the server asks for auth
    # when an unauthenticated request is made. This is required by ArcMap for
    # the basic auth scheme to work.
    authentication_classes = [
        BasicAuthentication, QueryKeyAuthentication,
        ExpiringTokenAuthentication, SessionAuthentication,
    ]

    def get(self, request):
        # Add auth key if provided in the original WMTS reuest.
        key = request.GET.get(GET_QUERY_PARAMETER_AUTH_KEY, None)

        # Get url base from request.
        host = request.get_host()
        protocol = 'http' if host == 'localhost' else 'https'
        urlbase = '{}://{}/api/'.format(protocol, host)

        # Get wmts layers for the request user.
        formulas = get_objects_for_user(request.user, 'formulary.view_formula', with_superuser=False)
        composites = get_objects_for_user(request.user, 'sentinel.view_composite', with_superuser=False)
        predictedlayers = get_objects_for_user(request.user, 'classify.view_predictedlayer', with_superuser=False)

        # Construct wmts layer list from wmts layers.
        layer_list = ''
        for composite in composites:
            for formula in formulas:
                # Generate formula tile url.
                url = '{urlbase}formula/{formula_id}/{layer_type}/{layer_id}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png?{keyname}={keyval}'.format(
                    urlbase=urlbase,
                    formula_id=formula.id,
                    layer_type='composite',
                    layer_id=composite.id,
                    keyname=GET_QUERY_PARAMETER_AUTH_KEY,
                    keyval=key,
                )
                layer_list += TILE_LAYER_TEMPLATE.format(
                    title='{} | {} - {}'.format(composite.name, formula.acronym, formula.name),
                    identifier='tesselo_{}_{}'.format(composite.id, formula.id),
                    url=url,
                )

        for pred in predictedlayers:
            url = "{urlbase}tile/{predictedlayer}/{{TileMatrix}}/{{TileCol}}/{{TileRow}}.png?{keyname}={keyval}".format(
                urlbase=urlbase,
                predictedlayer=pred.rasterlayer_id,
                keyname=GET_QUERY_PARAMETER_AUTH_KEY,
                keyval=key,
            )
            layer_list += TILE_LAYER_TEMPLATE.format(
                title=str(pred),
                identifier='tesselo_{}'.format(pred.id),
                url=url,
            )

        xml = WMTS_BASE_TEMPLATE.format(layers=layer_list, mat=self.tile_matrix_set_3857)
        xml = xml.replace('\n', '').replace('\r', '')

        return HttpResponse(xml, content_type="text/xml")

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


class WMTSLayerViewSet(PermissionsModelViewSet):
    queryset = WMTSLayer.objects.all().order_by('title')
    serializer_class = WMTSLayerSerializer
    _model = 'wmtslayer'
