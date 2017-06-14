define([
        'marionette',
        'auth/router',
        'explorer/router',
        'report/router',
        'report/views/report'
    ], function(
        Marionette,
        AuthRouter,
        ExplorerRouter,
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
        },

        onChildviewDidReport: function(data){
            data.model = new Backbone.Model({title: data.title, description: data.description});
            var report = new ReportView(data);
            this.showChildView('contentRegion', report);
            var url = '/report/' + encodeURIComponent(JSON.stringify(data));
            Backbone.history.navigate(url);
        }
    });
});

