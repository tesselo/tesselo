requirejs.config({
    paths: {
        jquery: '../../node_modules/jquery/dist/jquery',
        'jquery.cookie': '../../node_modules/jquery.cookie/jquery.cookie',
        bootstrap: '../../node_modules/bootstrap/dist/js/bootstrap',
        underscore: '../../node_modules/underscore/underscore',
        backbone: '../../node_modules/backbone/backbone',
        'backbone.babysitter': '../../node_modules/backbone.babysitter/lib/backbone.babysitter',
        'backbone.radio': '../../node_modules/backbone.radio/build/backbone.radio',
        'backbone.wreqr': '../../node_modules/backbone.wreqr/lib/backbone.wreqr',
        marionette: '../../node_modules/backbone.marionette/lib/backbone.marionette',
        text: '../../node_modules/requirejs-text/text',
        leaflet: '../../node_modules/leaflet/dist/leaflet',
        'leaflet.vectorgrid': '../../node_modules/leaflet.vectorgrid/dist/Leaflet.VectorGrid',
        'd3-color': '../../node_modules/d3-color/build/d3-color',
        'd3-interpolate': '../../node_modules/d3-interpolate/build/d3-interpolate',
        'd3-scale-chromatic': '../../node_modules/d3-scale-chromatic/build/d3-scale-chromatic',
        'nouislider': '../../node_modules/nouislider/distribute/nouislider',
        chartjs: '../../node_modules/chart.js/dist/Chart',
    },
    shim: {
        'bootstrap': {
            deps: ['jquery']
        },
        'jqyery.cookie': {
            deps: 'jquery'
        },
        'underscore': {
            exports: '_'
        },
        'backbone': {
            deps: ['underscore', 'jquery'],
            exports: 'Backbone'
        },
        'backbone.babysitter': {
            deps: ['backbone', 'underscore']
        },
        'backbone.radio': {
            deps: ['backbone', 'underscore']
        },
        'backbone.wreqr': {
            deps: ['backbone', 'underscore']
        },
        'marionette': {
            deps: ['backbone', 'backbone.radio', 'backbone.babysitter', 'backbone.wreqr'],
            exports: 'Marionette'
        },
        'leaflet': {
            exports: 'L'
        },
        'leaflet.vectorgrid': {
            deps: ['leaflet']
        }
    }
});

require([
        'app',
        'bootstrap'
    ], function(
        App
    ){
    App.start();
});
