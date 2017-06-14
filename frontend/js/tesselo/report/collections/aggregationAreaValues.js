define([
        'backbone',
        '../models/aggregationAreaValue'
    ], function(
        Backbone,
        AggregationAreaValue
    ){

    return Backbone.Collection.extend({
        model: AggregationAreaValue,
        url: '/api/valuecountresult',
        parse : function(data) {
            data = data.results;
            return _.filter(data, function(dat){ return !_.isEmpty(dat.value); });
        }
    });
});
