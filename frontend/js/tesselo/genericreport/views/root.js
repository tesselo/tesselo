define([
        'marionette'
    ], function(
        Marionette
    ){
    return Marionette.View.extend({
        template: _.template('<div class="report-container"></div>'),

        regions: {
            reportRegion: '.report-container'
        }
    });
});
