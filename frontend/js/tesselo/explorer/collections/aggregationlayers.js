define([
        'backbone'
    ],
    function(
        Backbone
    ){

    var Model = Backbone.Model.extend({
        urlRoot: '/api/aggregationlayer'
    });

    return Backbone.Collection.extend({
        model: Model,
        url: '/api/aggregationlayer'
    });
});

