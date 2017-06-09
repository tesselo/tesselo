define([
        'marionette',
        'controller',
        'genericreport/views/report'
    ], function(
        Marionette,
        ReportController,
        ReportView
    ){
    return Marionette.AppRouter.extend({
        controller: ReportController,
        appRoutes: {
            '(/)report/:reportdata': 'action',
        },
        initialize: function(options){
            this.controller.root = options.root;
        }
    });
});
