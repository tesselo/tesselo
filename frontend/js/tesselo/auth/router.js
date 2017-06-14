define([
        'marionette',
        'auth/login-view'
    ], function(
        Marionette,
        LoginView
    ){

    // Define Router
    var Controller = {
        actionLogin: function(){
            var login = new LoginView();
            this.root.showChildView('contentRegion', login);
        }
    }

    return Marionette.AppRouter.extend({
        controller: Controller,
        appRoutes: {
            'login': 'actionLogin'
        },
        initialize: function(root){
            this.controller.root = root;
        }
    });
});

