define([
        'marionette',
        'genericreport/views/report',
        './router',
    ], function(
        Marionette,
        ReportView,
        MapRouter
    ){
    return Marionette.View.extend({
        template: _.template('<div id="map"></div>'),

        regions: {
            mapRegion: '#map'
        },

        onRender: function() {
            var router = new MapRouter(this);
        },

        onChildviewDidReport: function(data){
            console.log('at root', data);
            data.model = new Backbone.Model({title: data.title, description: data.description});
            var report = new ReportView(data);
            this.showChildView('mapRegion', report);
        }
    });
});
