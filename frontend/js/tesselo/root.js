define([
        'marionette',
        'auth/router',
        'explorer/router',
        'scenes/router',
        'report/router',
        'report/views/report'
    ], function(
        Marionette,
        AuthRouter,
        ExplorerRouter,
        ScenesRouter,
        ReportRouter,
        ReportView
    ){
    return Marionette.View.extend({
        template: _.template('<div class="content"><h1>Welcome to Tesselo</h1></div>'),

        regions: {
            contentRegion: '.content'
        },

        onRender: function() {
            new AuthRouter(this);
            new ExplorerRouter(this);
            new ReportRouter(this);
            new ScenesRouter(this);
        },

        onChildviewDidReport: function(data){
            if(data.grouping == 'continuous' || data.grouping == 'discrete'){
                var url = '/report/scene/' + data.wlgrp + '/aggregationarea/' + data.aggregationlayer + '/formula/' + data.formula_id;
            } else {
                var url = '/report/' + encodeURIComponent(JSON.stringify(data));
            }
            data.model = new Backbone.Model({title: data.title, description: data.description});
            var report = new ReportView(data);
            this.showChildView('contentRegion', report);
            Backbone.history.navigate(url);
        }
    });
});

