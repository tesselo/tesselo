define([
        'backbone'
    ],
    function(
        Backbone
    ){

    var WLGModel = Backbone.Model.extend({
        urlRoot: '/api/worldlayergroup'
    });

    return Backbone.Collection.extend({
        model: WLGModel,
        url: '/api/worldlayergroup',
        parse : function(data) {
          return data.results;
        }
    });
});
