define([
        'marionette',
        'text!auth/login-template.html'
    ], function(
        Marionette,
        template
    ){
    return Marionette.View.extend({
        template: _.template(template),
        
        ui: {
            email: '.input-email',
            password: '.input-password',
            submit: '.input-submit'
        },

        events: {
            'click @ui.submit': 'submit'
        },

        submit: function(){
            var _this = this;
            $.ajax({
                url: "/login/",
                type: "POST",
                data: {
                    username: this.ui.email.val(),
                    password: this.ui.password.val()
                },
                cache: false,
                success: function() {
                    _this.trigger('login_successful');
                },
                error: function(){
                    alert('Login not successful, try again.')
                }
            });
        }
    });
});


