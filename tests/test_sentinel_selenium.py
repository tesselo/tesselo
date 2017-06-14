from unittest import skip

from selenium.webdriver import Remote
from selenium.webdriver.common.by import By
from selenium.webdriver.common.desired_capabilities import DesiredCapabilities
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from django.contrib.auth.models import User
from django.contrib.staticfiles.testing import LiveServerTestCase
from django.test.utils import override_settings


# os.environ['DJANGO_LIVE_TEST_SERVER_ADDRESS'] = 'web:8000'
# os.environ['DJANGO_LIVE_TEST_SERVER_ADDRESS'] = '0.0.0.0:8000'
# os.environ['DJANGO_LIVE_TEST_SERVER_ADDRESS'] = 'localhost:8000'
# from selenium.webdriver.firefox.webdriver import WebDriver

@skip('Not yet functional.')
@override_settings(CSRF_COOKIE_SECURE=False, SESSION_COOKIE_SECURE=False)
class IntegrationTests(LiveServerTestCase):
    """
    Integration tests that are run within the docker-compose setup.

    To run tests, use

    >> docker-compose -f docker-compose-test.yml run --rm web

    To debug tests, connect to an xtreminal view using vinagre

    >> vinagre 172.17.0.2:5900

    Where the ip address is the selenium container's address.
    """
    # live_server_url = 'http://{}:8000'.format(
    #     socket.gethostbyname(socket.gethostname())
    # )
    live_server_url = 'http://web:8000/'

    @classmethod
    def setUpClass(cls):
        print(cls.live_server_url)
        User.objects.create_superuser(
            username='lucille',
            email='lucille@bluth.com',
            password='shawnparmegian'
        )
        super(IntegrationTests, cls).setUpClass()
        cls.selenium = Remote(
            command_executor="http://selenium:4444/wd/hub",
            desired_capabilities=DesiredCapabilities.FIREFOX
        )
        # cls.selenium = WebDriver()

    @classmethod
    def tearDownClass(cls):
        cls.selenium.quit()
        super(IntegrationTests, cls).tearDownClass()

    def test_home(self):
        self.selenium.get(self.live_server_url)
        # Make sure page is loaded
        WebDriverWait(self.selenium, 5).until(
            EC.presence_of_element_located((By.NAME, "username"))
        )
        # Log in as lucille
        email_input = self.selenium.find_element_by_name("username")
        email_input.send_keys('lucille')
        password_input = self.selenium.find_element_by_name("password")
        password_input.send_keys('shawnparmegian')
        self.selenium.find_element_by_name('signin').click()
        # Make sure response has loaded
        WebDriverWait(self.selenium, 5).until(
            EC.presence_of_element_located((By.CLASS_NAME, "btn-rgb"))
        )
