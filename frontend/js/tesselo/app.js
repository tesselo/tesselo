define([
        'marionette',
        'views/root'
    ], function(
        Marionette,
        RootView
    ){
    // Instantiate marionette app
    var App = new Marionette.Application({
        region: '.main'
    });

    // Start backbone history on App start
    App.on('start', function(){
        var main = this.getRegion();
        main.show(new RootView());
        Backbone.history.start({pushState: false});
    });

    return App;
});

