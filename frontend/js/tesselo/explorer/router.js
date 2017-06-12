define([
        'marionette',
        './views/map'
    ], function(
        Marionette,
        MapView
    ){

    // Define Router
    var MapController = {
        actionMap: function(worldlayergroup, formula, scale_min, scale_max, scale_breaks, color, lat, lon, zoom){
            var map = new MapView({
                worldlayergroup: worldlayergroup,
                lat: lat,
                lon: lon,
                zoom: zoom,
                formula: formula,
                scale_min: scale_min,
                scale_max: scale_max,
                scale_breaks: scale_breaks,
                color: color
            });
            this.root.showChildView('contentRegion', map);
        }
    }

    return MainRouter = Marionette.AppRouter.extend({
        controller: MapController,
        appRoutes: {
            '(/)': 'actionMap',
            '(/)(:worldlayergroup)(/)(:formula)(/)(:scale_min)(/)(:scale_max)(/)(:scale_breaks)(/)(:color)(/)@:lat,:lon,:zoom': 'actionMap'
        },
        initialize: function(root){
            this.controller.root = root;
        }
    });
});
