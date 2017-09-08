define([
        'backbone'
    ],
    function(
        Backbone
    ){

    var Model = Backbone.Model.extend({
        urlRoot: '/api/formula'
    });

    return Backbone.Collection.extend({
        model: Model,
        url: '/api/formula',
        parse : function(data) {
          data.results.push({'name': 'RGB'});
          data.results.reverse();
          return data.results;
        }
    });
});

