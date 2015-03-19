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

class TestGsData(unittest.TestCase):

    def test_staff_sheet_read(self):
        from main import MainPage
        mp = MainPage()
        data = mp.get_staff_table()
        assert('username' in data[0])

class TestBadAuth(unittest.TestCase):

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
        # auth.AuthenticatedHandler.AUTH_METHOD = 'google'
        request = webapp2.Request.blank('/')
        response = request.get_response(application)
        assert('testuser is not authorized' in response.text)


class TestMain(unittest.TestCase):

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
        self.course_id = self.get_a_course_id()

    def setup_main_with_auth(self):
        from main import MainPage, auth, application
        def AlwaysAuthenticated(self):
            return 'testuser2'
        MainPage.AUTHORIZED_USERS = ['testuser2']
        auth.AuthenticatedHandler.Authenticate = AlwaysAuthenticated
        # auth.AuthenticatedHandler.AUTH_METHOD = 'google'
        self.application = application

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

    def test_main_page_good_auth(self):
        assert('<table id="table_id" class="display">' in self.response.text)

    def test_course_page(self):
        course_id = self.course_id
        request = webapp2.Request.blank('/course/' + course_id)
        response = request.get_response(self.application)
        assert('<h2>Content by chapter</h2>' in response.text)

    def test_course_stats(self):
        params = {'course_id': self.course_id}
        request = webapp2.Request.blank('/get/{course_id}/course_stats'.format(**params))
        response = request.get_response(self.application)
        data = json.loads(response.text)
        assert("stats_columns" in data)

    def test_usage_stats(self):
        params = {'course_id': self.course_id}
        request = webapp2.Request.blank('/get/{course_id}/usage_stats'.format(**params))
        response = request.get_response(self.application)
        # response.encoding = 'utf-8'
        # data = json.loads(response.text) # response.json
        data = response.json
        assert("data" in data)

    def test_activity_stats(self):
        params = {'course_id': self.course_id}
        request = webapp2.Request.blank('/get/{course_id}/activity_stats'.format(**params))
        response = request.get_response(self.application)
        # response.encoding = 'utf-8'
        # data = json.loads(response.text) # response.json
        data = response.json
        assert("series" in data)

    def test_ajax_table_data(self):
        params = {'course_id': self.course_id}
        data = {'draw': 2, 'start': 10, 'length': 10}
        request = webapp2.Request.blank('/get/{course_id}/user_info_combo/table_data'.format(**params), POST=data)
        response = request.get_response(self.application)
        data = response.json
        assert("draw" in data and data['draw']==2)

    def test_general_ajax_table_data(self):
        params = {'course_id': self.course_id}
        data = {'draw': 2, 'start': 10, 'length': 10}
        request = webapp2.Request.blank('/table/{course_id}/user_info_combo'.format(**params), POST=data)
        response = request.get_response(self.application)
        # print "general_ajax_table_data response=", response
        assert('.user_info_combo</title>' in str(response))

class TestAsCourseStaff(unittest.TestCase):

    def setUp(self):
        '''
        Views when authenticated as course staff (not instructor)
        '''
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
        self.course_id = self.get_a_course_id()

    def setup_main_with_auth(self):
        from main import MainPage, auth, application
        def AlwaysAuthenticated(self):
            return 'CourseStaff'
        auth.AuthenticatedHandler.Authenticate = AlwaysAuthenticated
        auth.local_config.STAFF_COURSE_TABLE = "file:test_staff_file.csv"
        self.application = application

    def get_a_course_id(self):
        request = webapp2.Request.blank('/')
        response = request.get_response(self.application)
        xml = etree.fromstring(response.text, parser=etree.HTMLParser())

        table = xml.find('.//table')
        rows = table.findall('.//tr')
        try:
            course_id = rows[1].findall('.//td')[-1].text
        except Exception as err:
            print "Oops - test failed - cannot get a course_id for user, response=", response
            print "table=%s, rows=%s" % (etree.tostring(table), etree.tostring(rows[1]))
            raise
        #print "rows4 ", etree.tostring(rows[4])
        print "course_id ", course_id
        self.response = response
        return course_id

    def test_main_page_good_auth(self):
        # print "test_main_page as course staff, response=", self.response
        assert('<table id="table_id" class="display">' in self.response.text)

    def test_general_ajax_table_data(self):
        params = {'course_id': self.course_id}
        data = {'draw': 2, 'start': 10, 'length': 10}
        request = webapp2.Request.blank('/table/{course_id}/user_info_combo'.format(**params), POST=data)
        response = request.get_response(self.application)
        # print "general_ajax_table response=", response
        assert('is not authorized to use this service' in str(response))

class TestAsResearcher(unittest.TestCase):

    def setUp(self):
        '''
        Views when authenticated as researcher
        '''
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
        self.course_id = self.get_a_course_id()

    def setup_main_with_auth(self):
        from main import MainPage, auth, application
        def AlwaysAuthenticated(self):
            return 'DrResearch'
        auth.AuthenticatedHandler.Authenticate = AlwaysAuthenticated
        auth.local_config.STAFF_COURSE_TABLE = "file:test_staff_file.csv"
        self.application = application

    def get_a_course_id(self):
        request = webapp2.Request.blank('/')
        response = request.get_response(self.application)
        xml = etree.fromstring(response.text, parser=etree.HTMLParser())

        table = xml.find('.//table')
        rows = table.findall('.//tr')
        try:
            course_id = rows[1].findall('.//td')[-1].text
        except Exception as err:
            print "Oops - test failed - cannot get a course_id for user, response=", response
            print "table=%s, rows=%s" % (etree.tostring(table), etree.tostring(rows[1]))
            raise
        #print "rows4 ", etree.tostring(rows[4])
        print "course_id ", course_id
        self.response = response
        return course_id

    def test_main_page_good_auth(self):
        # print "test_main_page as course staff, response=", self.response
        assert('<table id="table_id" class="display">' in self.response.text)

    def test_general_ajax_table_data(self):
        params = {'course_id': self.course_id}
        data = {'draw': 2, 'start': 10, 'length': 10}
        request = webapp2.Request.blank('/table/{course_id}/user_info_combo'.format(**params), POST=data)
        response = request.get_response(self.application)
        # print "general_ajax_table response=", response
        assert('.user_info_combo</title>' in str(response))
