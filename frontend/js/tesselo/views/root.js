define([
        'marionette',
        'auth/auth-router',
        'explorer/router'
    ], function(
        Marionette,
        AuthRouter,
        ExplorerRouter
    ){
    return Marionette.View.extend({
        template: _.template('<div class="content"><h1>Welcome to Tesselo</h1></div>'),
        regions: {
            contentRegion: '.content'
        },
        onRender: function() {
            new AuthRouter(this);
            new ExplorerRouter(this);
        }
    });
});

