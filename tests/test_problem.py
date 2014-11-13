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

class TestProblem(unittest.TestCase):

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
        self.course_table = table
        #print "rows4 ", etree.tostring(rows[4])
        print "course_id ", course_id
        self.response = response
        return course_id

    def get_chapter_with_problems(self):
        course_id = self.course_id
        request = webapp2.Request.blank('/get/%s/course_stats' % course_id)
        response = request.get_response(self.application)
        data = response.json
        # print json.dumps(data, indent=4)
        self.chapter_url_name = None
        for k in data['data']:
            if k['n_problem'] > 0:
                self.chapter_url_name = k['url_name']
                break
        print "chapter url_name = ", self.chapter_url_name

    def test_chapter_with_problems(self):
        self.get_chapter_with_problems()
        assert(self.chapter_url_name is not None)

    def get_problem_url(self):
        self.get_chapter_with_problems()
        params = {'course_id': self.course_id, 
                  'url_name': self.chapter_url_name,
        }
        request = webapp2.Request.blank('/get/{course_id}/{url_name}/chapter_stats'.format(**params))
        response = request.get_response(self.application)
        data = response.json['data']
        # print json.dumps(data, indent=4)
        self.problem_url_name = None
        for k in data:
            if (k['category']=='problem') and (k['nsubmissions']>0):
                self.problem_url_name = k['url_name']
        print "problem_url_name=", self.problem_url_name
        
    def test_chapter_page(self):
        self.get_problem_url()
        assert(self.problem_url_name is not None)
        
    def test_problem_page(self):
        self.get_problem_url()
        params = {'course_id': self.course_id, 
                  'url_name': self.problem_url_name,
        }
        request = webapp2.Request.blank('/get/{course_id}/{url_name}/problem_stats'.format(**params))
        response = request.get_response(self.application)
        data = response.json
        assert('data' in data)

        request = webapp2.Request.blank('/get/{course_id}/{url_name}/problem_histories'.format(**params))
        response = request.get_response(self.application)
        data = response.json
        assert('data' in data)
        assert('data_date' in data)
