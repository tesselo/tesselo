#!/usr/bin/env python
import os
import unittest

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException
from selenium.webdriver.chrome.options import Options


class TestTesseloAPI(unittest.TestCase):

    def setUp(self):
        options = Options()
        options.add_argument('--headless')
        self.browser = webdriver.Chrome(options=options)

    def testLoginTitle(self):
        self.browser.get('https://api.tesselo.com/api-auth/login/')
        self.assertEqual('Django REST framework', self.browser.title)

    @unittest.skipUnless('TEST_USER' in os.environ, 'Login test requires creds.')
    def testLogin(self):

        self.browser.get('https://stagingapi.tesselo.com/api-auth/login/')

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
