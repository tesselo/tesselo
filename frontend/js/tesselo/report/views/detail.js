define([
        'marionette',
        'chartjs',
        'leaflet',
        'text!../templates/detail.html'
], function(
    Marionette,
    Chart,
    L,
    detailTemplate
    ){

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
            var layers = _.map(this.options.layers, function(val, key){ return key + '=' + val; }).join();

            // Stringify legend dict.
            var legend = {};
            _.each(this.options.legend, function(leg){
                legend[leg.expression] = leg.color;
            });
            var legend = JSON.stringify(legend);

            // Setup query filter parameters for fetching agg data.
            var algebra_params = $.param({
                layers: layers,
                formula: this.options.formula,
                colormap: legend
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

            var data = _.zip(this.options.legend, this.model.get('ordered_values'));
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
        template: _.template('<h4>Table</h4><table><thead><tr><th>Color</th><th>Class</th><th>Value</th></tr></thead><tbody></tbody></table>'),

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
        template: _.template('<hr><h3><%- name %></h3><div class="row"><div class="arealist col-xs-4"></div><div class="areachart col-xs-4"></div><div class="areamap col-xs-4"></div></div>'),
        regions: {
            list: '.arealist',
            chart: '.areachart',
            map: '.areamap'
        },
        onRender: function(){
            // Construct list element data.
            var data = _.zip(this.options.legend, this.model.get('ordered_values'));
            data = _.map(data, function(dat){ dat[0].value = dat[1]; return dat[0]; });
            this.showChildView('list', new ListTableView({collection: new Backbone.Collection(data)}));

            this.showChildView('chart', new ChartView({model: this.model, legend: this.options.legend}));
            this.showChildView('map', new MapView({model: this.model, legend: this.options.legend, formula: this.options.formula, layers: this.options.layers}));
        }
    });

    const ItemView = Marionette.CollectionView.extend({
        childView: DetailView,
        childViewOptions: function(){
            return {
                legend: this.options.legend,
                layers: this.options.layers,
                formula: this.options.formula
            }
        }
    });

    return ItemView;
});