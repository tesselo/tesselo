define([
        'marionette',
        'd3-scale-chromatic',
        '../collections/worldlayergroups',
        '../collections/aggregationlayers',
        './picker',
        './world',
        './agglayer',
        'text!../templates/menu.html'
    ], function(
        Marionette,
        d3,
        WLGCollection,
        AggLayerCollection,
        PickerView,
        WorldView,
        AggLayerView,
        template
    ){
    return Marionette.View.extend({
        template: _.template(template),

        regions: {
            pickerRegion: '.color-picker',
            worldRegion: '.world-picker',
            aggLayerRegion: '.agglayer-picker'
        },

        ui: {
            rgb: '.rgb',
            rgb_btn: '.btn-rgb',
            formula: '.formula',
            formula_wrap: '.formula-wrap',
            refresh: '.refresh',
            scale_min: '.scale-min',
            scale_max: '.scale-max',
            scale_breaks: '.scale-breaks',
            report_toggle: '.report-toggle',
            report_wrap: '.report-wrap',
            report_show: '.report'
        },

        events: {
            'click @ui.refresh': 'setAlgebra',
            'click @ui.rgb': 'toggleRGB',
            'click @ui.report_toggle': 'reportToggle',
            'click @ui.report_show': 'report'
            //'keyup @ui.formula': 'setAlgebraByKey'
        },

        initialize: function(){
            _.bindAll(this, 'refresh', 'setLayerDict', 'report', 'reportToggle');
        },

        buildWorldPicker: function(){
            var _this = this;
            // Create collection and list view for world layer groups.
            var collection = new WLGCollection();
            var world = new WorldView({collection: collection});
            // Show world layer group view.
            this.showChildView('worldRegion', world);
            // Limit worldlayergroups to active layers.
            var params = {data: $.param({active: true})};
            // Fetch worldlayergroup data and set first layer.
            collection.fetch(params).done(function(){
                _this.setLayerDict(collection.models[0]);
                // Fetch child view for selected worldlayergroup, or the first one if not specified.
                if(_this.options.worldlayergroup){
                    var worldview = world.children.filter(function(view){  return view.model.id == _this.options.worldlayergroup; })[0];
                    // Fallback to first layer if id is not found.
                    if(!worldview){
                        var worldview = world.children.first();
                    }
                } else {
                    var worldview = world.children.first();
                }
                _this.setLayerDict(worldview.model);
                worldview.toggle();
            });
            // Hook worldlayergroup selector into map renderer.
            world.on('childview:world-changed', this.setLayerDict);
        },

        buildAggLayerPicker: function(){
            var _this = this;
            // Create collection and list view for world layer groups.
            var collection = new AggLayerCollection();
            var aggs = new AggLayerView({collection: collection});
            // Show agg layer view.
            this.showChildView('aggLayerRegion', aggs);
            // Fetch agglayer data and set first layer.
            collection.fetch().done(function(){
                aggs.children.first().toggle();
            });
            // Hook agglayer selector into map renderer.
            aggs.on('childview:agglayer-changed', function(model){
                _this.agglayer_id = model.id;
            });
        },

        setLayerDict: function(model){
            this.layer_dict = model.get('kahunas');
            this.worldlayergroup_id = model.id;
            this.refresh();
        },

        onRender: function(){

            var color_choices = new Backbone.Collection([
                    {'name': 'BrBG'},
                    {'name': 'PRGn'},
                    {'name': 'PiYG'},
                    {'name': 'PuOr'},
                    {'name': 'RdBu'},
                    {'name': 'RdGy'},
                    {'name': 'RdYlBu'},
                    {'name': 'RdYlGn'},
                    {'name': 'Spectral'},
                    {'name': 'Blues'},
                    {'name': 'Greens'},
                    {'name': 'Greys'},
                    {'name': 'Oranges'},
                    {'name': 'Purples'},
                    {'name': 'Reds'},
                    {'name': 'BuGn'},
                    {'name': 'BuPu'},
                    {'name': 'GnBu'},
                    {'name': 'OrRd'},
                    {'name': 'PuBuGn'},
                    {'name': 'PuBu'},
                    {'name': 'PuRd'},
                    {'name': 'RdPu'},
                    {'name': 'YlGnBu'},
                    {'name': 'YlGn'},
                    {'name': 'YlOrBr'},
                    {'name': 'YlOrRd'}
            ]);
            var picker = new PickerView({collection: color_choices, color: this.options.color});
            this.showChildView('pickerRegion', picker);
            picker.on('childview:colors-changed', this.refresh);

            if(this.options.formula){
                this.ui.formula.val(this.options.formula);
                this.ui.scale_min.val(this.options.scale_min);
                this.ui.scale_max.val(this.options.scale_max);
                this.ui.scale_breaks.val(this.options.scale_breaks > 0 ? this.options.scale_breaks : '');
                $(this.ui.rgb).children().toggleClass('btn-primary');
            }
            this.buildWorldPicker();
            this.buildAggLayerPicker();
        },

        toggleRGB: function(){
            $(this.ui.rgb).children().toggleClass('btn-primary');
            this.refresh();
        },

        setAlgebra: function(){
            if(this.ui.rgb_btn.hasClass('btn-primary')){
                $(this.ui.rgb).children().toggleClass('btn-primary');
            }
            this.refresh();
        },

        setAlgebraByKey: function(e){
            if(e.key == "Enter"){
                this.refresh();
            }
        },

        refresh: function(){
            if(Backbone.history.fragment){
                var urlsplit = Backbone.history.fragment.split('@');
                var coords = urlsplit[1] ? '@' + urlsplit[1] : '';
            }

            if(this.ui.rgb_btn.hasClass('btn-primary')){
                // Extract rgb channels from current world layer.
                var red = _.filter(this.layer_dict, function(val, key){ return key == 'B04.jp2' })[0];
                var green = _.filter(this.layer_dict, function(val, key){ return key == 'B03.jp2' })[0];
                var blue = _.filter(this.layer_dict, function(val, key){ return key == 'B02.jp2' })[0];

                this.ui.formula_wrap.hide();
                var url = '/api/algebra/{z}/{x}/{y}.png?layers=r=' + red + ',g=' + green + ',b=' + blue + '&scale=3e3';
                var nav_base = this.worldlayergroup_id + '/';
            } else {
                // Show formula container.
                this.ui.formula_wrap.show();
                // Construct ids array from current world layer.
                var ids = [];
                var _this = this;
                _.each(this.layer_dict, function(val, key){
                    // Remove jp2 from band names.
                    var name = key.split('.jp2')[0];
                    // Remove zero in band names.
                    name = name.split('0').join('');
                    // Filter bands that are in formula.
                    if(_this.ui.formula.val().indexOf(name) !== -1){
                        ids.push(name + '=' + val);
                    }
                });
                ids = ids.join(',');

                // Encode formula.
                var formula = encodeURIComponent(this.ui.formula.val().split(' ').join(''));

                // Get and encode colormap.
                var legend = this.colormap();
                legend = encodeURIComponent(JSON.stringify(legend));

                // Construct url.
                var url = '/api/algebra/{z}/{x}/{y}.png?layers=' + ids +'&formula=' + formula + '&colormap=' + legend;

                // Navigation base
                var min = parseFloat(this.ui.scale_min.val());
                var max = parseFloat(this.ui.scale_max.val());
                var brk = parseFloat(this.ui.scale_breaks.val());
                var colorview = this.getChildView('pickerRegion').children.filter(function(view){ return view.$el.hasClass('selected')})[0];
                var color = colorview.model.get('name');
                var nav_base = this.worldlayergroup_id + '/' + formula + '/' + min + '/' + max + '/' + (brk ? brk : '0') + '/' + color + '/';

            }

            this.triggerMethod('did:refresh', url);

            // Update navigation history
            Backbone.history.navigate(nav_base + coords);
        },

        colormap: function(brk){
            // Get d3 color scale using current selection.
            var colorview = this.getChildView('pickerRegion').children.filter(function(view){ return view.$el.hasClass('selected')})[0];
            var scale = d3['interpolate' + colorview.model.get('name')];

            // Get color min, max and breaks from ui.
            var min = parseFloat(this.ui.scale_min.val());
            var max = parseFloat(this.ui.scale_max.val());
            if(!brk){
                var brk = parseFloat(this.ui.scale_breaks.val());
            }

            var map = {};
            if(brk){
                // Use discrete color breaks.
                _.each(_.range(brk), function(i){
                    if(brk == 1){
                        // Set fraction to 1 if only one color has been requested.
                        var fraction = 1;
                    } else {
                        // Compute position in range.
                        var fraction = i / (brk - 1);
                    }
                    // Get color for that range and convert it to a simple RGBA array.
                    var color = scale(fraction);
                    color = color.replace('rgb', '').replace('(', '[').replace(')', ']');
                    color = JSON.parse(color);
                    color.push(255);
                    // Compute absolute break values based on range input.
                    var low = min + i * (max - min) / brk;
                    var high = min + (i + 1) * (max - min) / brk;

                    low = Math.round(low * 100) / 100;
                    high = Math.round(high * 100) / 100;

                    // Create algebra expression from values.
                    var expression = "(x>=" + low + ') & (x<' + high + ')';
                    // Add an entry to the colormap.
                    map[expression] = color;
                });
            } else {
                // If no number of breaks was specified, use continuous color scale.
                map['continuous'] = true;
                map['range'] = [min, max];
                map['from'] = JSON.parse(scale(0).replace('rgb', '').replace('(', '[').replace(')', ']'));
                map['to'] = JSON.parse(scale(1).replace('rgb', '').replace('(', '[').replace(')', ']'));
                map['over'] = JSON.parse(scale(0.5).replace('rgb', '').replace('(', '[').replace(')', ']'));
            }

            // Return encoded colormap.
            return map;
        },

        rgbToHex: function(r, g, b) {
            return "#" + ((1 << 24) + (r << 16) + (g << 8) + b).toString(16).slice(1);
        },

        reportToggle: function(){
            this.ui.report_wrap.toggle();
        },

        report: function(){
            var _this = this;

            var brk = parseFloat(this.ui.scale_breaks.val());
            brk = brk ? brk : 7;
            var legend = this.colormap(brk);
            legend = _.map(legend, function(val, key){
                return {
                    color: _this.rgbToHex(val[0], val[1], val[2]),
                    name: key,
                    expression: key
                }
            });

            var ids = {};
            _.each(this.layer_dict, function(val, key){
                // Remove jp2 from band names.
                var name = key.split('.jp2')[0];
                // Remove zero in band names.
                name = name.split('0').join('');
                // Filter bands that are in formula.
                if(_this.ui.formula.val().indexOf(name) !== -1){
                    ids[name] = val;
                }
            });

            var data = {
                layer_names: ids,
                formula: this.ui.formula.val(),
                grouping: legend,
                aggregationlayer: this.agglayer_id,
                zoom: 7,
                acres: 'True',
                title: 'Samba Report',
                description: 'Auto generated.'
            }

            this.triggerMethod('did:report', data);
        }
    });
});
