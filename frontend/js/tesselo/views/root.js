define([
        'marionette',
        'auth/auth-router'
    ], function(
        Marionette,
        AuthRouter
    ){
    return Marionette.View.extend({
        template: _.template('<div class="content"><h1>Welcome to Tesselo</h1></div>'),
        regions: {
            contentRegion: '.content'
        },
        onRender: function() {
            var router = new AuthRouter(this);
        }
    });
});

