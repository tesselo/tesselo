requirejs.config({
    paths: {
        jquery: '../../node_modules/jquery/dist/jquery',
        'jquery.cookie': '../../node_modules/jquery.cookie/jquery.cookie',
        underscore: '../../node_modules/underscore/underscore',
        backbone: '../../node_modules/backbone/backbone',
        'backbone.babysitter': '../../node_modules/backbone.babysitter/lib/backbone.babysitter',
        'backbone.radio': '../../node_modules/backbone.radio/build/backbone.radio',
        'backbone.wreqr': '../../node_modules/backbone.wreqr/lib/backbone.wreqr',
        marionette: '../../node_modules/backbone.marionette/lib/backbone.marionette',
        text: '../../node_modules/requirejs-text/text',
        leaflet: '../../node_modules/leaflet/dist/leaflet'
    },
    shim: {
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
        }
    }
});

require([
        'app'
    ], function(
        App
    ){
    App.start();
});

