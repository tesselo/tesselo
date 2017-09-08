define([
        'backbone'
    ],
    function(
        Backbone
    ){

    var WLGModel = Backbone.Model.extend({
        urlRoot: '/api/sentineltileaggregationarea'
    });

    return Backbone.Collection.extend({
        model: WLGModel,
        url: '/api/sentineltileaggregationarea',
        parse : function(data) {
            var results = _.map(data.results, function(result){
                // Replace prefix with nice date stamp.
                var split = result.name.split('/');
                var yr = split[4];
                var mo = split[5];
                mo = mo.length == 1 ? '0' + mo : mo;
                var da = split[6];
                da = da.length == 1 ? '0' + da : da;
                result.name = yr + '-' + mo + '-' + da;
                return result;
            });
            return _.sortBy(results, 'name');
        }
    });
});
