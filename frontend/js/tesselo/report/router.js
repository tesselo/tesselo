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
        },

        scene_report: function(scene, aggregationlayer, formula){
            var _this = this;

            $.get('/api/sentineltileaggregationarea/' + scene).done(function(scene){
                // Replace prefix with nice date stamp.
                var split = scene.name.split('/');
                var yr = split[4];
                var mo = split[5];
                mo = mo.length == 1 ? '0' + mo : mo;
                var da = split[6];
                da = da.length == 1 ? '0' + da : da;
                scene.name = yr + '-' + mo + '-' + da;

                $.get('/api/formula/' + formula).done(function(formula){
                    var ids = {};
                    _.each(scene.kahunas, function(val, key){
                        // Remove jp2 from band names.
                        var name = key.split('.jp2')[0];
                        // Remove zero in band names.
                        name = name.split('B0').join('B');
                        // Filter bands that are in formula.
                        if(formula.formula.indexOf(name) !== -1){
                            ids[name] = val;
                        }
                    });

                    var data = {
                        layer_names: ids,
                        formula: formula.formula,
                        grouping: 'continuous',
                        aggregationlayer: aggregationlayer,
                        zoom: 14,
                        acres: 'True',
                        title: formula.name + ' <span class="small pull-right">' + scene.name + '</span>',
                        description: formula.description,
                        color_palette: formula.color_palette,
                        min_val: formula.min_val,
                        max_val: formula.max_val,
                        hide_data_table: true
                    }
                    _this.report(data);
                });
            });
        }
    }

    return Marionette.AppRouter.extend({
        controller: ReportController,
        appRoutes: {
            'report/scene/(:scene_id)/aggregationarea/(:agg)/formula/(:formula)': 'scene_report',
            'report/(:reportdata)': 'action',
        },
        initialize: function(root){
            this.controller.root = root;
        }
    });
});
