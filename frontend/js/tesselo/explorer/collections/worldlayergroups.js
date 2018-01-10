define([
        'backbone'
    ],
    function(
        Backbone
    ){

    var WLGModel = Backbone.Model.extend({
        urlRoot: '/api/composite'
    });

    return Backbone.Collection.extend({
        model: WLGModel,
        url: '/api/composite',
        parse : function(data) {
          return data.results;
        }
    });
});
