define([
        'marionette',
        '../models/valueCountResult',
        '../collections/aggregationAreas',
        '../collections/valueCountResults',
        './detail',
        './table',
        './filter',
        'text!../templates/report.html'
    ], function(
        Marionette,
        ValueCountResult,
        AggregationAreas,
        ValueCountResults,
        DetailView,
        TableView,
        FilterView,
        reportTemplate
    ){
    return Marionette.View.extend({
        template: _.template(reportTemplate),

        regions: {
            filter: '.filters',
            detail: '.aggdetail',
            table: '.aggtable'
        },

        childViewEvents: {
            'filter': 'filter'
        },

        filter: function(sortBy){
            this.avals.comparator = sortBy;
            this.avals.sort();
        },

        onRender: function(){
            _.bindAll(this, 'processAvals', 'processAreas', 'processAll', 'filter');

            // Render Filter items.
            var filter = new FilterView({collection: new Backbone.Collection(this.options.grouping)});
            this.showChildView('filter', filter);
            filter.on('filter', this.filter);

            // Instantiate aggregation area values collection.
            this.avals = new ValueCountResults();

            // Stringify grouping dict.
            var grouping = JSON.stringify(this.options.grouping);

            // Setup query filter parameters for fetching agg data.
            var avals_params = {
                aggregationarea__aggregationlayer: this.options.aggregationlayer,
                layer_names: this.options.layer_names,
                formula: this.options.formula,
                grouping: JSON.stringify(this.options.grouping)
            };

            if(this.options.acres){
                avals_params.units = 'acres';
            };

            if(this.options.zoom){
                avals_params.zoom = this.options.zoom;
            };

            this.avals_params = avals_params;

            // Convert parameter dictionary into url ready string format.
            var query = _.clone(avals_params);
            query.layer_names = JSON.stringify(query.layer_names);
            var query = {data: $.param(query)}

            // Fetch the aggregation values.
            var _this = this;
            this.avals.fetch(query).done(_this.processAvals);

            // Fetch aggregation areas.
            this.areas = new AggregationAreas();
            var areas_params = {data: $.param({
                aggregationlayer: this.options.aggregationlayer
            })};
            this.areas.fetch(areas_params).done(_this.processAreas);
        },

        processAvals: function(){
            this.avals_done = true;
            this.processAll();
        },

        processAreas: function(){
            this.areas_done = true;
            this.processAll();
        },

        processAll: function(areas){
            if(!this.areas_done || !this.avals_done) return;
            var _this = this;
            // Find avals that do not exist yet and create those.
            this.areas.each(function(area){
                var aval = _this.avals.filter(function(aval){
                    return aval.get('aggregationarea') == area.id;
                });
                if(!aval.length){
                    var data = _.clone(_this.avals_params);
                    data.aggregationarea = area.id;
                    var result = new ValueCountResult(data)
                    _this.avals.add(result);
                    result.save();
                }
            });

            // Combine the two collections.
            this.avals.each(function(aval){
                // Get area matching this aval.
                var area = _this.areas.filter(function(area){ return area.id == aval.get('aggregationarea'); })[0];

                // Set area name and geometry as model attributes.
                aval.set('name', area.get('name'));
                aval.set('geom', area.get('geom'));

                // Compute value list ordered by grouping entry order and set as attribute.
                var ordered_values = [];
                var ordered_values = _.map(_this.options.grouping, function(leg){
                    return _.filter(aval.get('value') , function(val, key){ return  key == leg.expression; })[0];
                });
                aval.set('ordered_values', ordered_values);
            });

            // Compute unique list of classes from grouping.
            var names = _.pluck(this.options.grouping, 'name');

            // Construct and render details.
            var aggdetail = new DetailView({collection: this.avals, grouping: this.options.grouping, layer_names: this.options.layer_names, formula: this.options.formula});
            this.showChildView('detail', aggdetail);

            // Construct and render table.
            var aggtable = new TableView({collection: this.avals, model: new Backbone.Model({names: names})});
            this.showChildView('table', aggtable);
        }
    });
});
