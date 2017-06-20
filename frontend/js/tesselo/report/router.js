define([
        'marionette',
        './views/report',
        './views/input'
    ], function(
        Marionette,
        ReportView,
        InputView
    ){
    var ReportController = {
        action: function(reportdata){
            if(reportdata){
                var data = JSON.parse(decodeURIComponent(reportdata));
                this.report(data);
            } else {
                var input = new InputView();
                input.on('report', this.report, this)
                this.root.showChildView('contentRegion', input);
            }
        },

        report: function(data){
            data.model = new Backbone.Model({title: data.title, description: data.description});
            var report = new ReportView(data);
            this.root.showChildView('contentRegion', report);
        }
    }

    return Marionette.AppRouter.extend({
        controller: ReportController,
        appRoutes: {
            'report/(:reportdata)': 'action',
        },
        initialize: function(root){
            this.controller.root = root;
        }
    });
});
