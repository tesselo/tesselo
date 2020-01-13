const x = require('casper').selectXPath

const utils = require('utils')

const setup = require('../setup')

// Get authentication credentials from command line args.
const creds = setup.get_creds(casper);

const has_creds = creds.username && creds.password;

casper.test.begin('Tesselo API is up and running', has_creds ? 3 : 0 , function suite(test) {

    casper.start(setup.get_base_url(casper) + 'api-auth/login/?next=/');

    // Skip these tests if
    casper.thenBypassIf(function(){ return !has_creds }, 5);

    casper.then(function() {
      casper.fill('form', {
        'username': creds.username,
        'password': creds.password
      }, true);
    });

    casper.wait(500);

    casper.then(function() {
      test.assertTitle("Tesselo REST API", "Tesselo API title is the one expected");
    });

    casper.then(function(){
      casper.click('a[href*=formula]')
    });

    casper.then(function() {
      test.assertTextExists('Formula List');
      test.assertExists('form[enctype*=multipart]');
      casper.fill('form[enctype*=multipart]', {
        'name': 'Test Formula',
        'acronym': 'test',
        'formula': 'B1',
        'min_val': 0,
        'max_val': 1,
        'breaks': 0
      }, false)
    });

    casper.run(function() {
        test.done();
    });
});
