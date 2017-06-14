define([
        'marionette',
        '../collections/aggregationAreas',
        '../collections/aggregationAreaValues',
        './detail',
        './table',
        './filter',
        'text!../templates/report.html'
    ], function(
        Marionette,
        AggregationAreas,
        AggregationAreaValues,
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
            _.bindAll(this, 'processAvals', 'filter');

            // Render Filter items.
            var filter = new FilterView({collection: new Backbone.Collection(this.options.legend)});
            this.showChildView('filter', filter);
            filter.on('filter', this.filter);

            // Instantiate aggregation area values collection.
            this.avals = new AggregationAreaValues();

            // Deconstruct layers dict into a query parameter.
            var layers = _.map(this.options.layers, function(val, key){ return key + '=' + val; }).join();

            // Stringify legend dict.
            var legend = JSON.stringify(this.options.legend);

            // Setup query filter parameters for fetching agg data.
            var avals_params = {
                aggregationlayer: this.options.aggregationlayer,
                layers: layers,
                formula: this.options.formula,
                grouping: legend
            };

            if(this.options.acres){
                avals_params.acres = 'True';
            };

            if(this.options.maxzoom){
                avals_params.maxzoom = this.options.maxzoom;
            };

            // Convert parameter dictionary into url ready string format.
            avals_params = {data: $.param(avals_params)};

            // Fetch the aggregation values.
            var _this = this;
            this.avals.fetch(avals_params).done(_this.processAvals);

            // Fetch aggregation areas.
            this.areas = new AggregationAreas();
            var areas_params = {data: $.param({
                aggregationlayer: this.options.aggregationlayer
            })};
            this.areas.fetch(areas_params).done(_this.processAvals);
            //this.areas.fetch(areas_params).done(_this.processAvals);
        },

        requestAvals: function(areas){
            this.areas.each(function(area){
                console.log('area', area);
            })
        },

        processAvals: function(values){
            if(!this.avals.length || !this.areas.length) return;
            var _this = this;

            //this.avals = this.avals.filter()
            console.log(this.avals, this.areas);
            //this.avals = this.avals.filter(function(dat){ return !_.isEmpty(dat.get('value')); });
            //console.log(this.avals)

            // Combine the two collections.
            this.avals.each(function(aval){
                // Get area matching this aval.
                var area = _this.areas.filter(function(area){ return area.id == aval.id; })[0];

                // Set area name and geometry as model attributes.
                aval.set('name', area.get('name'));
                aval.set('geom', area.get('geom'));

                // Compute value list ordered by legend entry order and set as attribute.
                var ordered_values = [];
                var ordered_values = _.map(_this.options.legend, function(leg){
                    return _.filter(aval.get('value') , function(val, key){ return  key == leg.expression; })[0];
                });
                aval.set('ordered_values', ordered_values);
            });

            // Compute unique list of classes from legend.
            var names = _.pluck(this.options.legend, 'name');

            // Construct and render details.
            var aggdetail = new DetailView({collection: this.avals, legend: this.options.legend, layers: this.options.layers, formula: this.options.formula});
            this.showChildView('detail', aggdetail);

            // Construct and render table.
            var aggtable = new TableView({collection: this.avals, model: new Backbone.Model({names: names})});
            this.showChildView('table', aggtable);
        }
    });
});
