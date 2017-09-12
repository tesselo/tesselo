define([
        'marionette',
        'chartjs',
        'leaflet',
        'd3-scale-chromatic'
], function(
    Marionette,
    Chart,
    L,
    d3
    ){

    const relative_palette = 'RdYlBu';

    const MapView = Marionette.View.extend({
        template: _.template('<h4>Minimap</h4><div class="minimap" style="width: 100%; height: 300px;"></div>'),
        ui: {
            map: '.minimap'
        },
        onAttach: function(){
            // Get aggregation area geometry from model
            var agg = L.geoJson(this.model.get('geom'), {
                style: {
                    weight: 2,
                    opacity: 0.7,
                    color: '#333',
                    fillOpacity: 0.2,
                    fillColor: '#333'
                }
            });

            // Instantiate leaflet map, padding by 10%
            var bounds = agg.getBounds().pad(0.2);
            var LMap = L.map(this.ui.map[0], {
                //zoom: 8,
                minZoom: 0,
                maxZoom: 15,
                maxBounds: bounds,
                scrollWheelZoom: false,
                attributionControl: false,
                zoomControl: true
            }).fitBounds(bounds);

            // Base layer
            var basemap = L.tileLayer('http://{s}.basemaps.cartocdn.com/light_nolabels/{z}/{x}/{y}.png',{
              attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="http://cartodb.com/attributions">CartoDB</a>'
            }).addTo(LMap);

            // Labelmap with streets
            var labelmap = L.tileLayer('http://{s}.basemaps.cartocdn.com/light_only_labels/{z}/{x}/{y}.png',{
              attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors, &copy; <a href="http://cartodb.com/attributions">CartoDB</a>'
            }).addTo(LMap);

            // Make sure streets are overlaid on top
            LMap.getPanes().overlayPane.appendChild(labelmap.getContainer());
            labelmap.setZIndex(9999);

            // Add aggregation area to map
            LMap.addLayer(agg);

            // Deconstruct layers dict into a query parameter.
            var layers = _.map(this.options.layer_names, function(val, key){ return key + '=' + val; }).join();

            // Stringify grouping dict.
            var colormap = {};
            if(this.options.grouping == 'continuous' || this.options.grouping == 'discrete'){

                colormap['continuous'] = true;
                if(this.options.absolute){
                    var scale = d3['interpolate' + this.options.color_palette];
                    colormap['range'] = [this.options.min_val, this.options.max_val];
                } else {
                    var scale = d3['interpolate' + relative_palette];
                    colormap['range'] = [this.model.get('min'), this.model.get('max')];
                }
                colormap['from'] = JSON.parse(scale(0).replace('rgb', '').replace('(', '[').replace(')', ']'));
                colormap['to'] = JSON.parse(scale(1).replace('rgb', '').replace('(', '[').replace(')', ']'));
                colormap['over'] = JSON.parse(scale(0.5).replace('rgb', '').replace('(', '[').replace(')', ']'));
            } else {
                _.each(this.options.grouping, function(leg){
                    colormap[leg.expression] = leg.color;
                });
            }
            var colormap = JSON.stringify(colormap);

            // Setup query filter parameters for fetching agg data.
            var algebra_params = $.param({
                layers: layers,
                formula: this.options.formula,
                colormap: colormap
            });

            // Add raster algebra layer.
            var url = '/api/algebra/{z}/{x}/{y}.png?' + algebra_params;
            L.tileLayer(url).addTo(LMap);
        }
    });

    const ChartView = Marionette.View.extend({
        template: _.template('<h4>Chart</h4><canvas class="report-chart"></canvas>'),
        
        ui: {
            chart: '.report-chart'
        },

        onRender: function(){
            var _this = this;
            if(this.options.grouping == 'continuous' || this.options.grouping == 'discrete'){
                if(_this.options.absolute){
                    var scale = d3['interpolate' + this.options.color_palette];
                } else {
                    var scale = d3['interpolate' + relative_palette];
                }

                var data = _.map(this.model.get('value'), function(val, key){
                    var bla = parseFloat(key.split(',')[0].split('(')[1]);
                    bla = Math.round(bla * 100) / 100;
                    return {color: 'gray', name: bla, value: val};
                });
                
                data = _.sortBy(data, 'name');

                data = {
                    labels: _.pluck(data, 'name'),
                    datasets: [{
                        data: _.pluck(data, 'value'),
                        backgroundColor: _.map(_.pluck(data, 'name'), function(val){
                            if(_this.options.absolute){
                                return scale((val - _this.options.min_val) / (_this.options.max_val - _this.options.min_val));
                            } else {
                                return scale((val - _this.model.get('min')) / (_this.model.get('max') - _this.model.get('min')));
                            }
                        })
                    }]
                };
                var totalschart = new Chart(this.ui.chart, {
                    type: 'bar',
                    data: data,
                    options: {
                        legend: {
                            display: false
                        }
                    }
                });

            } else {
                var data = _.zip(this.options.grouping, this.model.get('ordered_values'));
                data = _.map(data, function(dat){ return {name: dat[0].name, color: dat[0].color, value: dat[1]}; })
                data = _.filter(data, function(dat){ return dat.value; });
                var data = {
                    labels: _.pluck(data, 'name'),
                    datasets: [{
                        data: _.pluck(data, 'value'),
                        backgroundColor: _.pluck(data, 'color')
                    }]
                };
                var totalschart = new Chart(this.ui.chart, {
                    type: 'doughnut',
                    data: data,
                    options: {
                        legend: {
                            display: false
                        }
                    }
                });
            }
        }
    });

    const ListView = Marionette.View.extend({
        tagName: 'tr',
        template: _.template('<td><div class="detail-colorbox" style="background-color: <%- color %>"></div></td><td><%- name %></td><td><%- value %></td>')
    });

    const ListCollectionView = Marionette.CollectionView.extend({
        tagName: 'tbody',
        childView: ListView
    });

    const ListTableView = Marionette.View.extend({
        className: 'table table-hover',
        template: _.template('<h4>Table</h4><table class="table"><thead><tr><th>Color</th><th>Class</th><th>Hectares</th></tr></thead><tbody></tbody></table>'),

        regions: {
            body: {
                el: 'tbody',
                replaceElement: true
            }
        },

        onAttach: function() {
            this.showChildView('body', new ListCollectionView({
                collection: this.collection
            }));
        }
    });

    const DetailView = Marionette.View.extend({
        template: _.template('<hr><h3><%- name %><span class="pull-right"><small><%- status %></small></span></h3><div class="row"><div class="arealist col-xs-4"></div><div class="areachart col-xs-4"></div><div class="areamap col-xs-4"></div></div>'),
        regions: {
            list: '.arealist',
            chart: '.areachart',
            map: '.areamap'
        },
        onRender: function(){
            var _this = this;

            if(this.options.grouping == 'continuous' || this.options.grouping == 'discrete'){
                if(_this.options.absolute){
                    var scale = d3['interpolate' + this.options.color_palette];
                } else {
                    var scale = d3['interpolate' + relative_palette];

                }

                var reshaped_data = _.sortBy(_.map(this.model.get('value'), function(val, key){
                    var from = parseFloat(key.split(',')[0].split('(')[1]);
                    from = Math.round(from * 100) / 100;
                    var to = parseFloat(key.split(',')[1].split(')')[0]);
                    to = Math.round(to * 100) / 100;
                    if(_this.options.absolute){
                        var color = scale((from - _this.options.min_val) / (_this.options.max_val - _this.options.min_val));
                    } else {
                        var color = scale((from - _this.model.get('min')) / (_this.model.get('max') - _this.model.get('min')));
                    }
                    return {color: color, name: from + ' - ' + to, value: val, from: from};
                }), 'from');

                this.showChildView('list', new ListTableView({
                    collection: new Backbone.Collection(reshaped_data),
                    color_palette: this.options.color_palette,
                    absolute: this.options.absolute,
                    max_val: this.options.max_val,
                    min_val: this.options.min_val
                }));
                this.showChildView('chart', new ChartView({
                    model: this.model,
                    grouping: this.options.grouping,
                    color_palette: this.options.color_palette,
                    absolute: this.options.absolute,
                    max_val: this.options.max_val,
                    min_val: this.options.min_val
                }));
                this.showChildView('map', new MapView({
                    model: this.model,
                    grouping: this.options.grouping,
                    formula: this.options.formula,
                    layer_names: this.options.layer_names,
                    color_palette: this.options.color_palette,
                    absolute: this.options.absolute,
                    max_val: this.options.max_val,
                    min_val: this.options.min_val
                }));
            } else {
                // Construct list element data.
                var data = _.zip(this.options.grouping, this.model.get('ordered_values'));
                data = _.map(data, function(dat){ dat[0].value = dat[1]; return dat[0]; });
                this.showChildView('list', new ListTableView({collection: new Backbone.Collection(data)}));
                this.showChildView('chart', new ChartView({model: this.model, grouping: this.options.grouping}));
                this.showChildView('map', new MapView({model: this.model, grouping: this.options.grouping, formula: this.options.formula, layer_names: this.options.layer_names}));
            }
        }
    });

    const ItemView = Marionette.CollectionView.extend({
        childView: DetailView,
        childViewOptions: function(){
            return {
                absolute: this.options.absolute,
                max_val: this.options.max_val,
                min_val: this.options.min_val,
                grouping: this.options.grouping,
                layer_names: this.options.layer_names,
                formula: this.options.formula,
                color_palette: this.options.color_palette
            }
        }
    });

    return ItemView;
});
