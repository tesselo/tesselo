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
            data = data.results;
            // Convert data into hectares.
            _.each(data, function(dat){
                _.each(dat.value, function(val, key){
                    dat.value[key] = Math.round(val * 0.404686);
                });
            });
            return data;
        }
    });
});
