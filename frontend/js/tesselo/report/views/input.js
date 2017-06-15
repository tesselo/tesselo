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
            layer_names: '.layer-names-input',
            formula: '.formula-input',
            grouping: '.grouping-input',
            agglayer: '.agglayer-input',
            maxzoom: '.maxzoom-input',
            title: '.title-input',
            description: '.description-input',
            report: '.report'
        },

        report: function(){
            var data = {
                layer_names: JSON.parse(this.ui.layer_names.val()),
                formula: this.ui.formula.val(),
                grouping: JSON.parse(this.ui.grouping.val()),
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
