const setup = require('../setup')

casper.test.begin('Tesselo login form works (currently mainly disabled)', 1, function suite(test) {

    casper.start(setup.get_base_url(casper) + "app/login", function() {
      // this.sendKeys('input[name="username"]', "lucille@bluth.com", {keepFocus: true})
      // this.sendKeys('input[name="password"]', "iloveshawnparmegian23", {keepFocus: true})
      // this.sendKeys('input[name="password"]', casper.page.event.key.Enter, {keepFocus: true});
      // this.sendKeys('.login-button', casper.page.event.key.Enter, {keepFocus: true});
      // console.log('username', this.evaluate(function() {
      //   return document.querySelector('input[name="username"]').value
      // }))
      // console.log('password', this.evaluate(function() {
      //   return document.querySelector('input[name="password"]').value
      // }))
      //
      // casper.click('.login-button');
      //
      casper.wait(500);
      casper.then(function() {
        test.assertExists('.login-button');
      });
    });

    // casper.then(function() {
    //
    //   console.log(casper.evaluate(function(){
    //     return document.body.innerHTML;
    //   }));
    //
    //   test.assertTextExists('Unable to log in with provided credentials.');
    //
    //   test.assertExists('.menu', 'Map menu exists');
    // });

    casper.run(function() {
        test.done();
    });
});
