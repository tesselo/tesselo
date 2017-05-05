require(['jquery', 'backbone', 'jquery.cookie'], function($, Backbone){
    var _sync = Backbone.sync;
    Backbone.sync = function(method, model, options){
        options.beforeSend = function(xhr){
            var token = $.cookie('csrftoken')
            xhr.setRequestHeader('X-CSRFToken', token);
        };
        return _sync(method, model, options);
    };

    // https://docs.djangoproject.com/en/dev/ref/contrib/csrf/#ajax
    function csrfSafeMethod(method) {
        return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
    }

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
                var token = $.cookie('csrftoken')
                xhr.setRequestHeader("X-CSRFToken", token);
            }
        }
    });

    // Setup page tracking function
    Backbone.history.ga = function(){
        if(typeof ga != 'undefined'){
            ga('send', 'pageview', {'page': location.pathname + location.search + location.hash});
        }
    };
});
