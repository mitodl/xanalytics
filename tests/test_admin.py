import unittest
from google.appengine.api import memcache
from google.appengine.ext import ndb
from google.appengine.ext import testbed
import json

import pytest
import StringIO
import webapp2
from webtest import TestApp
from webtest import Upload
from lxml import etree

import local_config

class TestAdmin(unittest.TestCase):

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

    def test_admin_page_bad_auth(self):
        from main import MainPage, auth, application
        def AlwaysAuthenticated(self):
            return 'pmuser'
        auth.AuthenticatedHandler.Authenticate = AlwaysAuthenticated
        auth.local_config.STAFF_COURSE_TABLE = "file:test_staff_file.csv"
        # auth.AuthenticatedHandler.AUTH_METHOD = 'google'
        request = webapp2.Request.blank('/admin')
        response = request.get_response(application)
        assert('pmuser is not authorized' in response.text)

    def setup_main_with_auth(self):
        from main import MainPage, auth, application
        def AlwaysAuthenticated(self):
            return 'testuser2'
        MainPage.AUTHORIZED_USERS = ['testuser2']
        auth.AuthenticatedHandler.Authenticate = AlwaysAuthenticated
        # auth.AuthenticatedHandler.AUTH_METHOD = 'google'
        self.application = application

    def test_admin_page_load(self):
        self.setup_main_with_auth()
        request = webapp2.Request.blank('/admin')
        response = request.get_response(self.application)
        assert('Analytics Dashbboard Admin Page' in response.text)
        assert("file:test_staff_file.csv" in response.text)

        request = webapp2.Request.blank('/admin', POST={'action': "Reload staff table"})
        response = request.get_response(self.application)
        assert("Staff table reloaded" in response.text)

        request = webapp2.Request.blank('/admin', POST={'action': "Reload course listings"})
        response = request.get_response(self.application)
        assert("Course listings reloaded" in response.text)
