module.exports = {
  get_base_url: function(casper){
    const stage = casper.cli.get('stage')
    if ( stage == 'dev' || stage == 'staging') {
      const url = 'https://' + stage + '.tesselo.com/'
    } else {
      const url = 'https://tesselo.com/'
    }
    casper.echo('Using ' + url)
    return url
  }
}
