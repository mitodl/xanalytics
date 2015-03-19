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

class TestDashboard(unittest.TestCase):

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
        self.setup_main_with_auth()

    def setup_main_with_auth(self):
        from dashboard import Dashboard, auth
        from main import application
        def AlwaysAuthenticated(self):
            return 'testuser2'
        Dashboard.AUTHORIZED_USERS = ['testuser2']
        auth.AuthenticatedHandler.Authenticate = AlwaysAuthenticated
        # auth.AuthenticatedHandler.AUTH_METHOD = 'google'
        self.application = application

    def test_dashboard_page(self):
        request = webapp2.Request.blank('/dashboard')
        response = request.get_response(self.application)
        assert('All-Course Dashboard' in response.text)

    def test_dashboard_geo_stats(self):
        request = webapp2.Request.blank('/dashboard/get/geo_stats')
        response = request.get_response(self.application)
        data = response.json
        assert("totals" in data)

    def test_dashboard_broad_stats(self):
        request = webapp2.Request.blank('/dashboard/get/broad_stats')
        response = request.get_response(self.application)
        data = response.json
        assert("table" in data)

    def test_dashboard_enrollment(self):
        request = webapp2.Request.blank('/dashboard/get/enrollment_by_time')
        response = request.get_response(self.application)
        data = response.json
        assert("series" in data)

    def test_dashboard_courses_by_time(self):
        request = webapp2.Request.blank('/dashboard/get/courses_by_time')
        response = request.get_response(self.application)
        data = response.json
        assert("series" in data)

