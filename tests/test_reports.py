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

class TestCustomReports(unittest.TestCase):

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

    def setup_main_with_auth(self, username='testuser2'):
        from main import MainPage, auth, application
        from custom_reports import CustomReportPages
        from admin import AdminPages
        auth.local_config.STAFF_COURSE_TABLE = "file:test_staff_file.csv"
        def AlwaysAuthenticated(self):
            return username
        CustomReportPages.AUTHORIZED_USERS = ['testuser2']
        MainPage.AUTHORIZED_USERS = ['testuser2']
        AdminPages.AUTHORIZED_USERS = ['testuser2']
        auth.AuthenticatedHandler.Authenticate = AlwaysAuthenticated
        self.application = application

    def test_custom_reports_load(self):
        self.setup_main_with_auth()
        request = webapp2.Request.blank('/custom')
        response = request.get_response(self.application)
        # print response.text
        assert('Download ALL Reports' in response.text)

    def do_import(self):
        self.setup_main_with_auth()
        rfn = "data/ANALYTICS_REPORT_enrollment-by-day-for-course-from-sql.yaml"
        data = open(rfn).read()
        request = webapp2.Request.blank('/custom', POST={'overwrite': "no", 
                                                         'action': 'Upload Custom Report(s)',
                                                         'file': data })
        response = request.get_response(self.application)
        return response

    def test_custom_reports_import(self):
        response = self.do_import()
        assert("Successfully imported report"  in response.text)

    def get_a_course_id(self):
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

    def load_staff_table(self):
        # load staff table
        request = webapp2.Request.blank('/admin', POST={'action': "Reload staff table"})
        response = request.get_response(self.application)
        assert("Staff table reloaded" in response.text)

    def test_custom_report_html(self):
        import urllib
        self.setup_main_with_auth()
        self.course_id = self.get_a_course_id()
        response = self.do_import()
        report_name = "enrollment-by-day-for-course-from-sql"
        query = urllib.urlencode({'course_id': self.course_id})
        request = webapp2.Request.blank('/page/%s?%s' % (report_name, query))
        request.method = "GET"
        response = request.get_response(self.application)
        assert("#table-enrollment-by-day-for-course-from-sql"  in response.text)
        
        self.load_staff_table()

        # switch user to being an instructor 
        self.setup_main_with_auth('teacher')
        response = request.get_response(self.application)
        assert("Sorry, teacher is not authorized to use this service"  in response.text)

        # switch user to being a PM
        self.setup_main_with_auth('pmuser')
        response = request.get_response(self.application)
        assert("#table-enrollment-by-day-for-course-from-sql"  in response.text)
        
        # switch course_id
        self.setup_main_with_auth('teacher')
        self.course_id = 'MITx/6.SFMx/1T2014'
        query = urllib.urlencode({'course_id': self.course_id})
        request = webapp2.Request.blank('/page/%s?%s' % (report_name, query))
        response = request.get_response(self.application)
        assert("#table-enrollment-by-day-for-course-from-sql"  in response.text)
        
