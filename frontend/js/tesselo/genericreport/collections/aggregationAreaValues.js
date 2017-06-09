define([
        'backbone',
        'genericreport/models/aggregationAreaValue'
    ], function(
        Backbone,
        AggregationAreaValue
    ){

    return Backbone.Collection.extend({
        model: AggregationAreaValue,
        url: '/api/aggregationareavalue'
        //parse : function(data) {
            //return _.filter(data, function(dat){ return !_.isEmpty(dat.value); });
        //}
    });
});
