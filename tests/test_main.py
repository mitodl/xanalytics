import unittest
from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed

import pytest
import StringIO
import webapp2
from webtest import TestApp
from webtest import Upload
from lxml import etree

import local_config

class TestClass(unittest.TestCase):

    def setUp(self):
        self.testbed = testbed.Testbed()
        # Then activate the testbed, which prepares the service stubs for use.
        self.testbed.activate()
        # Next, declare which service stubs you want to use.
        self.testbed.init_datastore_v3_stub()
        self.testbed.init_memcache_stub()
        self.testbed.init_urlfetch_stub()

        from google.appengine.api.app_identity import app_identity_stub
        from google.appengine.api.app_identity import app_identity_keybased_stub
        email_address = local_config.SERVICE_EMAIL
        private_key_path = local_config.SERVICE_KEY_FILE
        stub = app_identity_keybased_stub.KeyBasedAppIdentityServiceStub(email_address=email_address,
                                                                         private_key_path=private_key_path)
        self.testbed._register_stub(testbed.APP_IDENTITY_SERVICE_NAME, stub)

    def test_main_page_bad_auth(self):
        from main import MainPage, auth, application
        def AlwaysAuthenticated(self):
            return 'testuser'
        auth.AuthenticatedHandler.Authenticate = AlwaysAuthenticated
        request = webapp2.Request.blank('/')
        response = request.get_response(application)
        assert('testuser is not authorized' in response.text)

    def setup_main_with_auth(self):
        from main import MainPage, auth, application
        def AlwaysAuthenticated(self):
            return 'testuser2'
        MainPage.AUTHORIZED_USERS = ['testuser2']
        auth.AuthenticatedHandler.Authenticate = AlwaysAuthenticated
        self.application = application

    def get_a_course_id(self):
        self.setup_main_with_auth()
        request = webapp2.Request.blank('/')
        response = request.get_response(self.application)
        xml = etree.fromstring(response.text, parser=etree.HTMLParser())
        table = xml.find('.//table')
        rows = table.findall('.//tr')
        course_id = rows[4].findall('.//td')[-1].text
        #print "rows4 ", etree.tostring(rows[4])
        print "course_id ", course_id
        self.response = response
        return course_id

    def test_main_page_good_auth(self):
        self.get_a_course_id()
        assert('<table id="table_id" class="display">' in self.response.text)

    def test_course_page(self):
        course_id = self.get_a_course_id()
        self.setup_main_with_auth()
        request = webapp2.Request.blank('/course/' + course_id)
        response = request.get_response(self.application)
        assert('<h2>Content by chapter</h2>' in response.text)

