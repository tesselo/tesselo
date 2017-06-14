define([
        'backbone',
        '../models/aggregationArea'
    ], function(
        Backbone,
        AggregationArea
    ){

    return Backbone.Collection.extend({
        model: AggregationArea,
        url: '/api/aggregationarea'
        //parse : function(data) {
            //return data.results;
        //}
    });
});
