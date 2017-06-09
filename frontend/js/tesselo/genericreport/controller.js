define([
        'marionette',
        'genericreport/views/report',
        'genericreport/views/input'
    ], function(
        Marionette,
        ReportView,
        InputView
    ){
    return Controller = {
        action: function(reportdata){
            if(reportdata){
                var data = JSON.parse(decodeURIComponent(reportdata));
                this.report(data);
            } else {
                var input = new InputView();
                input.on('report', this.report, this)
                this.root.showChildView('reportRegion', input);
            }
        },

        report: function(data){
            data.model = new Backbone.Model({title: data.title, description: data.description});
            var report = new ReportView(data);
            this.root.showChildView('reportRegion', report);
            Backbone.history.navigate(encodeURIComponent(JSON.stringify(data)));
        }
    }
});
