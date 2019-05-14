const x = require('casper').selectXPath

const setup = require('../setup')

casper.test.begin('Tesselo homepage is up and running', 1, function suite(test) {

    casper.start(setup.get_base_url(casper), function() {
        test.assertTitle("Tesselo", "Tesselo homepage title is the one expected");
    });

    casper.run(function() {
        test.done();
    });
});
