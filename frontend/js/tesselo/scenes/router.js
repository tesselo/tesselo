define([
        'marionette',
        './views/map'
    ], function(
        Marionette,
        MapView
    ){

    // Define Router
    var MapController = {
        actionMap: function(lat, lon, zoom){
            var map = new MapView({
                lat: lat,
                lon: lon,
                zoom: zoom
            });
            this.root.showChildView('contentRegion', map);
        }
    }

    return Marionette.AppRouter.extend({
        controller: MapController,
        appRoutes: {
            '': 'actionMap',
            'scenes': 'actionMap',
            'scenes@:lat,:lon,:zoom': 'actionMap'
        },
        initialize: function(root){
            this.controller.root = root;
        }
    });
});
