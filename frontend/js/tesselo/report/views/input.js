define([
        'marionette',
        'text!../templates/input.html'
    ], function(
        Marionette,
        template
    ){
    return Marionette.View.extend({
        template: _.template(template),

        initialize: function(){
            _.bindAll(this, 'report');
        },

        events: {
            'click @ui.report': 'report'
        },

        ui: {
            layers: '.layer-input',
            formula: '.formula-input',
            legend: '.legend-input',
            agglayer: '.agglayer-input',
            maxzoom: '.maxzoom-input',
            title: '.title-input',
            description: '.description-input',
            report: '.report'
        },

        report: function(){
            var data = {
                layers: JSON.parse(this.ui.layers.val()),
                formula: this.ui.formula.val(),
                legend: JSON.parse(this.ui.legend.val()),
                aggregationlayer: this.ui.agglayer.val(),
                maxzoom: this.ui.maxzoom.val(),
                title: this.ui.title.val(),
                description: this.ui.description.val()
            }
            this.trigger('report', data);
            Backbone.history.navigate('/report/' + encodeURIComponent(JSON.stringify(data)));
        }
    });
});
