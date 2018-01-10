define([
        'marionette',
        './views/map'
    ], function(
        Marionette,
        MapView
    ){

    // Define Router
    var MapController = {
        actionMap: function(composite, formula, scale_min, scale_max, scale_breaks, color, lat, lon, zoom){
            var map = new MapView({
                composite: composite,
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

    return Marionette.AppRouter.extend({
        controller: MapController,
        appRoutes: {
            'mosaic': 'actionMap',
            '(/)(:composite)(/)(:formula)(/)(:scale_min)(/)(:scale_max)(/)(:scale_breaks)(/)(:color)(/)@:lat,:lon,:zoom': 'actionMap'
        },
        initialize: function(root){
            this.controller.root = root;
        }
    });
});
