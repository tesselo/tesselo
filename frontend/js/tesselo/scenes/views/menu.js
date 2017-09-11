define([
        'marionette',
        'd3-scale-chromatic',
        '../collections/worldlayergroups',
        '../collections/aggregationlayers',
        '../collections/formulas',
        './world',
        './formulas',
        './agglayer',
        'text!../templates/menu.html'
    ], function(
        Marionette,
        d3,
        WLGCollection,
        AggLayerCollection,
        FormulaCollection,
        WorldView,
        FormulaView,
        AggLayerView,
        template
    ){
    return Marionette.View.extend({
        template: _.template(template),

        regions: {
            pickerRegion: '.color-picker',
            worldRegion: '.world-picker',
            aggLayerRegion: '.agglayer-picker',
            formulaRegion: '.formula-list'
        },

        ui: {
            report_toggle: '.report-toggle',
            report_wrap: '.report-wrap',
            report_show: '.report'
        },

        events: {
            'click @ui.report_toggle': 'reportToggle',
            'click @ui.report_show': 'report'
        },

        initialize: function(){
            _.bindAll(this, 'refresh', 'setLayerDict','setFormulaModel', 'report', 'reportToggle');
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
                worldview.toggle();
            });
            // Hook worldlayergroup selector into map renderer.
            world.on('childview:world-changed', this.setLayerDict);
        },

        buildFormulaPicker: function(){
            var _this = this;
            // Create collection and list view
            var collection = new FormulaCollection();
            var form = new FormulaView({collection: collection});
            // Show world layer group view.
            this.showChildView('formulaRegion', form);
            // Limit worldlayergroups to active layers.
            var params = {data: $.param({active: true})};
            // Fetch worldlayergroup data and set first layer.
            collection.fetch(params).done(function(){
                // Fetch child view for selected worldlayergroup, or the first one if not specified.
                if(_this.options.formula){
                    var formulaview = form.children.filter(function(view){  return view.model.id == _this.options.worldlayergroup; })[0];
                    // Fallback to first layer if id is not found.
                    if(!formulaview){
                        var formulaview = form.children.first();
                    }
                } else {
                    // Default to RGB.
                    var formulaview = form.children.filter(function(view){ return view.model.get('acronym') == 'RGB'; })[0];
                }
                _this.setFormulaModel(formulaview.model, true);
                formulaview.toggle();
            });
            // Hook worldlayergroup selector into map renderer.
            form.on('childview:formula-changed', this.setFormulaModel);
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
            this.layer_dict_date = model.get('name');
            this.layer_dict = model.get('kahunas');
            this.worldlayergroup_id = model.id;
            this.refresh();
        },

        setFormulaModel: function(model, not_refresh){
            this.formula_model = model;
            if(!not_refresh){
                this.refresh();
            }
        },

        onRender: function(){
            this.buildWorldPicker();
            this.buildFormulaPicker();
            this.buildAggLayerPicker();
        },

        refresh: function(){
            if(!this.formula_model) return;
            if(!this.layer_dict) return;

            if(Backbone.history.fragment){
                var urlsplit = Backbone.history.fragment.split('@');
                var coords = urlsplit[1] ? '@' + urlsplit[1] : '';
            }

            if(this.formula_model.get('acronym') == 'RGB'){
                // Extract rgb channels from current world layer.
                var red = _.filter(this.layer_dict, function(val, key){ return key == 'B04.jp2' })[0];
                var green = _.filter(this.layer_dict, function(val, key){ return key == 'B03.jp2' })[0];
                var blue = _.filter(this.layer_dict, function(val, key){ return key == 'B02.jp2' })[0];

                var url = '/api/algebra/{z}/{x}/{y}.png?layers=r=' + red + ',g=' + green + ',b=' + blue + '&scale=3e3';
                var nav_base = this.worldlayergroup_id + '/';
            } else {
                // Construct ids array from current world layer.
                var ids = [];
                var _this = this;
                _.each(this.layer_dict, function(val, key){
                    // Remove jp2 from band names.
                    var name = key.split('.jp2')[0];
                    // Remove zero in band names.
                    name = name.split('B0').join('B');
                    // Filter bands that are in formula.
                    if(_this.formula_model.get('formula').indexOf(name) !== -1){
                        ids.push(name + '=' + val);
                    }
                });
                ids = ids.join(',');

                // Encode formula.
                var formula = encodeURIComponent(this.formula_model.get('formula').split(' ').join(''));

                // Get and encode colormap.
                var legend = this.colormap();
                legend = encodeURIComponent(JSON.stringify(legend));

                // Construct url.
                var url = '/api/algebra/{z}/{x}/{y}.png?layers=' + ids +'&formula=' + formula + '&colormap=' + legend;

                // Navigation base
                //var nav_base = this.worldlayergroup_id + '/' + formula + '/' + min + '/' + max + '/' + (brk ? brk : '0') + '/' + color + '/';

            }

            this.triggerMethod('did:refresh', url);

            // Update navigation history
            //Backbone.history.navigate(nav_base + coords);
        },

        colormap: function(brk){
            // Get d3 color scale using current selection.
            var scale = d3['interpolate' + this.formula_model.get('color_palette')];

            // Get color min, max and breaks from ui.
            var min = parseFloat(this.formula_model.get('min_val'));
            var max = parseFloat(this.formula_model.get('max_val'));
            if(!brk){
                var brk = parseFloat(this.formula_model.get('breaks'));
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

            var brk = parseFloat(this.formula_model.get('breaks'));
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
                name = name.split('B0').join('B');
                // Filter bands that are in formula.
                if(_this.formula_model.get('formula').indexOf(name) !== -1){
                    ids[name] = val;
                }
            });

            var data = {
                layer_names: ids,
                formula: this.formula_model.get('formula'),
                grouping: 'continuous',
                //grouping: legend,
                aggregationlayer: this.agglayer_id,
                zoom: 14,
                acres: 'True',
                title: this.formula_model.get('name') + ' <span class="small pull-right">' + this.layer_dict_date + '</span>',
                description: this.formula_model.get('description'),
                color_palette: this.formula_model.get('color_palette'),
                hide_data_table: true
            }

            this.triggerMethod('did:report', data);
        }
    });
});
