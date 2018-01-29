var sys = require('system');
var cname = sys.env.EB_FUTURE_ENV_CNAME;

var url = "https://tesselo.com/api-auth/login";

casper.test.begin('Test login', function suite(test) {
    casper.start(url, function() {
        casper.waitForSelector('form', function() {
            test.assertExists('form', 'Login form exists.');
            this.fill('form', {
                username: "lucille",
                password: "shawnparmegian"
            }, true);
        });
    });

    casper.waitForSelector('.text-error', function() {
        test.assertTextExists('Please enter a correct username and password. Note that both fields may be case-sensitive.', 'Form contains login error message');
    });

    casper.run(function() {
        test.done();
    });
});
