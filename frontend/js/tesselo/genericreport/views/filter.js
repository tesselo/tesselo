define([
        'marionette',
        'text!genericreport/templates/filter.html'
], function(
    Marionette,
    filterTemplate
    ){

    // Plot checkboxes for each legend entry.
    const LegendFilterItemView = Marionette.View.extend({
        template: _.template('<input type="checkbox" value="<%= expression %>"><%= name %>'),
        triggers: {
            change: 'change'
        }
    });

    const LegendFilterCollectionView = Marionette.CollectionView.extend({
        childView: LegendFilterItemView
    });

    // Plot radio buttons for each aggregator, and add the legend checkbox view.
    return Marionette.View.extend({
        template: _.template(filterTemplate),

        regions: {
            legend: {
                el: '.legendfilter',
                replaceElement: true
            }
        },

        ui: {
            sort_order: '.sort_order',
            aggregation_options: '.aggregation_options'
        },

        onAttach: function() {
            // Render legend checkoboxes.
            var legend = new LegendFilterCollectionView({
                collection: this.collection
            });
            this.showChildView('legend', legend);
        },

        events: {
            'change': 'change'
        },

        childViewEvents: {
            'change': 'change'
        },

        change: function(data){
            // Get expression values for the selected models.
            var view = this.getChildView('legend');

            var legend_selected = view.children.filter(function(dat){
                return dat.$el.find('input').prop('checked');
            }).map(function(dat){
                return dat.model.get('expression');
            });

            // Create the aggregation function options lookups.
            var sum = function(data) { return _.reduce(data, function(memo, num){ return memo + num; }, 0); };
            var avg = function(data) { return sum(data) / data.length; };
            var function_lookup = {
                sum: sum,
                avg: avg
            };

            // Get aggregation function based on radio buttons ui.
            var funk = function_lookup[this.ui.aggregation_options.find('input:radio:checked').val()];

            // Get sort order from ui.
            var sort_order = this.ui.sort_order.find('input:radio:checked').val();

            // Create a sort by function based on the above selection.
            var sortBy = function(model){
                // Get aggregation values for the selected legend items.
                var elements = _.map(legend_selected, function(exp) { var val = model.get('value')[exp]; return val ? val : 0; });
                // Filter zero elements.
                elements = _.filter(elements, function(elm) { return elm; });
                // Aggregate based on the selected function.
                var result = funk(elements);
                // Return aggregate to be sorted on, using sort order flag.
                return sort_order * result;
            }
            this.trigger('filter', sortBy);
        }
    });
});
