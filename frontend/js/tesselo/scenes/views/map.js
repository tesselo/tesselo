define([
        'marionette',
        'leaflet',
        './menu',
        './slider',
        'leaflet.vectorgrid'
    ],
    function(
        Marionette,
        L,
        MenuView,
        SliderView
    ){

    const VectorStyle = {
        fill: false,
        weight: 5,
        fillColor: '#3333FF',
        color: '#BB2222',
        fillOpacity: 0.3,
        opacity: 0.8
    };

    //const VectorHighlight = { ...VectorStyle, fillColor: '#990000'};

    return Marionette.View.extend({
        className: 'map',

        template: _.template('<div id="menu" class="scene-menu"></div><div class="opacity-slider"></div>'),

        regions: {
            menuRegion: '#menu',
            sliderRegion: '.opacity-slider'
        },

        initialize: function(){
            _.bindAll(this, 'moveend', 'setOpacity', 'buildMap', 'buildMenu');
        },

        onChildviewDidRefresh: function(url){
            var current_opacity = 1;

            // Remove current layer.
            if(this.map.hasLayer(this.layer)){
                current_opacity = this.layer.options.opacity;
                this.map.removeLayer(this.layer);
            }

            // Add new layer.
            this.layer = L.tileLayer(url, {opacity: current_opacity});
            this.layer.addTo(this.map);
        },

        onChildviewAgglayerChanged: function(model){
            var _this = this;
            this.mouse_is_over = false;
            // Remove current layer.
            if(this.map.hasLayer(this.vtiles)){
                this.map.removeLayer(this.vtiles);
            }
            // Dont add layer for the "none selected" choice.
            if(typeof model.id == 'undefined') return;
            // Create style sheet with the new layer name.
            var style = {};
            style[model.get('name')] = VectorStyle;
            // Create vector tile layer.
            this.vtiles = L.vectorGrid.protobuf('/api/vtiles/' + model.id + '/{z}/{x}/{y}.pbf', {
                fetchOptions: {credentials: 'same-origin'},
                getFeatureId: function(f) {
                    return f.properties.id;
                },
                interactive: true,
                vectorTileLayerStyles: style,
                zIndex: 9999,
            })
            .on('click', function(e){
                console.log('Should report', e.layer.properties.id);
            })
            .addTo(this.map);
            //.on('mouseover', function(e) {
                //console.log('mouse', _this.mouse_is_over);
                //if(_this.mouse_is_over) return;
                //_this.mouse_is_over = true;
                //this.setFeatureStyle(e.layer.properties.id, VectorHighlight);
            //})
            //.on('mouseout', function(e){
                //console.log('mouseout')
                //_this.mouse_is_over = false;
                //this.resetFeatureStyle(e.layer.properties.id);
            //})
        },

        onChildviewDidReport: function(data){
            this.triggerMethod('did:report', data);
        },

        onAttach: function(){
            this.buildMap();
            this.buildMenu();
        },

        buildMap: function(){
            // Create Leaflet Map
            var view = [
                this.options.lat ? this.options.lat : 2.1145187790090134,
                this.options.lon ? this.options.lon : 36.930198669433594
            ];
            var zoom = this.options.zoom ? this.options.zoom : 2;
            var map = L.map(this.el, {
                attributionControl: true,
            }).setView(view, zoom);

            map.attributionControl.setPrefix(null);

            L.tileLayer(
                'https://tiles.wmflabs.org/bw-mapnik/{z}/{x}/{y}.png',
                {
                    attribution: '&copy; <a href="http://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }
            ).addTo(map);


            // Attach map to object.
            this.map = map;

            // Hook maps into functionality, construct coordinates.
            map.on('moveend', this.moveend);
            this.moveend();
        },

        buildMenu: function(){
            var menu = new MenuView({
                worldlayergroup: this.options.worldlayergroup,
                formula: this.options.formula,
                scale_min: this.options.scale_min,
                scale_max: this.options.scale_max,
                scale_breaks: this.options.scale_breaks,
                color: this.options.color
            });
            this.showChildView('menuRegion', menu);

            var slider = new SliderView();
            this.showChildView('sliderRegion', slider);
            slider.on('slider-update', this.setOpacity);

            var _this=this;
            _.each([slider.el, menu.el], function(elm){
                var info = L.DomUtil.get(elm);

                // Disable dragging when user's cursor enters the element
                info.addEventListener('mouseover', function () {
                    _this.map.dragging.disable();
                    _this.map.doubleClickZoom.disable();
                    _this.map.scrollWheelZoom.disable();
                });

                // Re-enable dragging when user's cursor leaves the element
                info.addEventListener('mouseout', function () {
                    _this.map.dragging.enable();
                    _this.map.doubleClickZoom.enable();
                    _this.map.scrollWheelZoom.enable();
                });
            })
        },

        moveend: function(){
            var center = this.map.getCenter(),
            lat = center.lat,
            lng = center.lng,
            zoom = this.map.getZoom();

            if(Backbone.history.fragment){
                var urlsplit = Backbone.history.fragment.split('@');
                var base = urlsplit[0];
            } else {
                var base = 'scenes';
            }

            Backbone.history.navigate(base + '@' + lat + ',' + lng + ',' + zoom);
        },

        setOpacity: function(val){
            this.layer.setOpacity(val/100);
        }
    });
});
