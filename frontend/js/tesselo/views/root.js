define([
        'marionette'
    ], function(
        Marionette
    ){
    return Marionette.View.extend({
        template: _.template('<div class="content"><h1>Welcome to Tesselo</h1></div>'),
        regions: {
            mapRegion: '.content'
        }
    });
});

