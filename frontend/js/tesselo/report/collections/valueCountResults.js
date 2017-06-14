define([
        'backbone',
        '../models/valueCountResult'
    ], function(
        Backbone,
        ValueCountResult
    ){

    return Backbone.Collection.extend({
        model: ValueCountResult,
        url: '/api/valuecountresult',
        parse : function(data) {
            return data.results;
            //return _.filter(data, function(dat){ return !_.isEmpty(dat.value); });
        }
    });
});
