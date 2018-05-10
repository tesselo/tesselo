var x = require('casper').selectXPath;

casper.test.begin('Tesselo homepage is up and running', 6, function suite(test) {

    casper.start("https://staging.tesselo.com/", function() {
        test.assertTitle("Tesselo", "Tesselo homepage title is the one expected");
        test.assertExists('.btn-outline', "Main button is found");
        test.assertTextExists('Tesselo is backed by the European Space Agency (ESA) through the ESA BIC Portugal program.');
        test.assertExists({
          type: 'xpath',
          path: '//a[@href="/app/"]'
        }, "Found launch link");
        casper.click(x('//a[@href="/app/"]'));
    });

    casper.then(function() {
      test.assertExists('form.login-form', 'Login form exists');
      test.assertExists('button.login-button', 'Login button exists');
    });

    casper.run(function() {
        test.done();
    });
});
