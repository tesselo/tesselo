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
        url: '/api/aggregationlayer',
        parse : function(data) {
            var results =  _.sortBy(data.results, 'name');
            results = results.reverse();
            results.push({'name': '-----'});
            results = results.reverse();
          return results;
        }
    });
});
