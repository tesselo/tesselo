#!/usr/bin/env python
import os
import unittest

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.firefox.options import Options


class TestTesseloAPI(unittest.TestCase):

    def setUp(self):
        options = Options()
        options.add_argument('--headless')
        self.browser = webdriver.Firefox(options=options)
        # Set appropriate api endpoint.
        self.stage = os.environ.get('STAGE')
        if self.stage == 'production':
            api_prefix = ''
        else:
            api_prefix = self.stage
        self.api = 'https://{}api.tesselo.com/'.format(api_prefix)

    def testLoginTitle(self):
        self.browser.get('{}accounts/login/'.format(self.api))
        self.assertEqual('Tesselo REST API', self.browser.title)

    def testAPINothAuthenticated(self):
        self.browser.get(self.api)
        self.assertIn('Authentication credentials were not provided.', self.browser.page_source)

    @unittest.skipUnless('TEST_USER' in os.environ, 'Login test requires creds.')
    def testLogin(self):

        self.browser.get('{}accounts/login/'.format(self.api))

        usrname = self.browser.find_element_by_css_selector('#id_username')
        usrname.send_keys(os.environ.get('TEST_USER'))

        password = self.browser.find_element_by_css_selector('#id_password')
        password.send_keys(os.environ.get('TEST_PASSWORD'))

        self.browser.find_element_by_css_selector('#submit-id-submit').click()

        self.assertEqual('Tesselo REST API', self.browser.title)

        self.browser.find_element_by_css_selector('a[href*=formula]').click()

        body = self.browser.find_element_by_tag_name('body')

        self.assertIn('Formula List', body.text)

        try:
            self.browser.find_element_by_css_selector('form[enctype*=multipart]')
        except NoSuchElementException:
            self.fail('Formula multipart form not found.')

    def tearDown(self):
        self.browser.quit()


if __name__ == '__main__':
    unittest.main()
