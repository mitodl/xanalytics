import csv
import datetime
import json
import logging
import os
import re
import urllib
import urlparse
import webapp2
import local_config

import gsdata

from pytz.gae import pytz
from webapp2_extras import sessions
from collections import defaultdict

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext import webapp
from google.appengine.ext.ndb import msgprop
from protorpc import messages 

from google.appengine.api import memcache

mem = memcache.Client()

#-----------------------------------------------------------------------------

class GeneralFunctions(object):

    @staticmethod
    def TheNow():
        tz = pytz.timezone('US/Eastern')
        n = datetime.datetime.utcnow().replace(tzinfo = pytz.utc)
        return n.astimezone(tz)

#-----------------------------------------------------------------------------

def auth_and_role_required(role=''):
    def role_required_decorator(handler):
        """
        Decorator that checks if there's a user associated with the current session,
        and that the user has authorization to see the specified course_id content.
        Will fail if there's no session present.

        Also requires the user to hold a particular role, if specified.
        """
        def check_login(self, *args, **kwargs):
            redirect = self.do_auth()
            if redirect:
                return redirect()
            if ('org' in kwargs) and ('number' in kwargs) and ('semester' in kwargs):
                course_id = '/'.join([kwargs[x] for x in ['org', 'number', 'semester']])
            else:
                course_id = None
            if not self.is_user_authorized_for_course(course_id):
                return self.no_auth_sorry()

            if role:
                if not self.does_user_have_role(role, course_id):
                    return self.no_auth_sorry()

            return handler(self, *args, **kwargs)
    
        return check_login
    return role_required_decorator

def auth_required(handler):
    """
    Decorator that checks if there's a user associated with the current session.
    Will also fail if there's no session present.
    """
    def check_login(self, *args, **kwargs):
        redirect = self.do_auth()
        if redirect:
            return redirect()
        if ('org' in kwargs) and ('number' in kwargs) and ('semester' in kwargs):
            course_id = '/'.join([kwargs[x] for x in ['org', 'number', 'semester']])
        else:
            course_id = None
        if not self.is_user_authorized_for_course(course_id):
            return self.no_auth_sorry()
        return handler(self, *args, **kwargs)

    return check_login

#-----------------------------------------------------------------------------

class AuthenticatedHandler(webapp2.RequestHandler, GeneralFunctions):
    CAS_URL = local_config.CAS_URL
    AUTH_METHOD = local_config.AUTH_METHOD
    AUTHORIZED_USERS = local_config.STAFF_USERS

    def do_auth(self):
        user = self.Authenticate()
        self.user = user
        self.common_data['user'] = self.user
        if user is None:
            return self.do_cas_redirect
        return None

    def is_superuser(self):
        return self.user in self.AUTHORIZED_USERS        

    def no_auth_sorry(self):
        self.response.write("Sorry, %s is not authorized to use this service" % self.user)

    def get_staff_table(self):
        '''
        Get staff user table, a list of dicts.
        dicts should have "username", "role", and "course_id" as keys.  May also have "notes" key.
        '''
        scdt = getattr(local_config, 'STAFF_COURSE_TABLE', None)
        data = []
        m = re.match('docs:([^:]+):([^:]+)', scdt)
        if m:
            # staff file is a google doc spreadsheet
            fname = m.group(1)
            sheet = m.group(2)
            data = gsdata.cached_get_datasheet(fname, sheet)['data']
        elif scdt is not None:
            (dataset, table) = scdt.split('.')
            data = self.cached_get_bq_table(dataset, table)['data']        
        cnt = 1
        toremove = []
        for elem in data:
            elem['sid'] = cnt 
            if not elem['username'] or (elem['username'].startswith('-')):	# drop all entris with username starting with dash
                toremove.append(elem)
            cnt += 1
        for elem in toremove:	# remove after labeling all the sid's
            data.remove(elem)
        return data

    def disable_staff_table_entry(self, index):
        '''
        "delete" (really, disable) a staff table entry by prepending the username with a minnus sign.
        Works only with the google spreadsheet staff backend.
        '''
        scdt = getattr(local_config, 'STAFF_COURSE_TABLE', None)
        m = re.match('docs:([^:]+):([^:]+)', scdt)
        if not m:
            logging.error('Attempted to disable staff table entry index=%s, but not using google spreadsheet backend!' % index)
            return
        fname = m.group(1)
        sheet = m.group(2)
        stable = self.get_staff_table()
        theent = None
        for ent in stable:
            if ent['sid']==index:
                theent = ent
        if theent is None:
            logging.error('Attempted to disable non-existent staff entry, or one already disabled, index=%s' % index)
            return
        gsdata.modify_datasheet_acell(fname, sheet, "A%d" % (index+1), "-" + theent['username'])

        # flush cache, to force reload
        memset = 'docs:%s.%s' % (fname, sheet)
        mem.delete(memset)        


    def add_staff_table_entry(self, data):
        '''
        Add staff table entry.
        Works only with the google spreadsheet staff backend.
        '''
        scdt = getattr(local_config, 'STAFF_COURSE_TABLE', None)
        m = re.match('docs:([^:]+):([^:]+)', scdt)
        if not m:
            logging.error('Attempted to add staff table entry %s, but not using google spreadsheet backend!' % data)
            return
        fname = m.group(1)
        sheet = m.group(2)
        stable = self.get_staff_table()
        fields = ['username', 'role', 'course_id', 'notes']
        newrow = [data[x] for x in fields]
        newpos = stable[-1]['sid']+1
        gsdata.append_row_to_datasheet(fname, sheet, newrow)

        # flush cache, to force reload
        memset = 'docs:%s.%s' % (fname, sheet)
        mem.delete(memset)        


    def get_staff_course_table(self):
        '''
        Create the local "staff_course_table" which has (username, course_id) in staff_course_table['user_course']
        and (username) in staff_course_table['user'].
        '''
        memset = 'staff_course_table'
        staff_course_table = mem.get(memset)
        scdt = getattr(local_config, 'STAFF_COURSE_TABLE', None)
        if (not staff_course_table) and (scdt is not None) and (scdt):
            staff = self.get_staff_table()
            staff_course_table = {'user_course': {}, 'user': defaultdict(list)}
            for k in staff:
                staff_course_table['user_course'][(k['username'], k['course_id'])] = k
                staff_course_table['user'][k['username']].append(k)
            mem.set(memset, staff_course_table, time=3600*12)
            logging.info('staff_course_table = %s' % staff_course_table.keys())
        return staff_course_table

    def does_user_have_role(self, role, course_id=None):
        '''
        Return True if user has specified role.
        '''
        if self.is_superuser():
            return True
        staff_course_table = self.get_staff_course_table()
        users = staff_course_table['user']
        if not self.user in users:
            return False
        for uent in users[self.user]:		# each entry is a dict, with keys course_id, role, and notes
            if uent['role']==role:
                if course_id is None:
                    return True
                if not uent['course_id']:	# if empty, then role is global across all courses
                    return True
                if uent['course_id']==course_id:
                    return True
        return False

    def is_user_authorized_for_course(self, course_id=None):
        '''
        Return True if user is authorized for the course.
        '''
        if self.is_superuser():
            return True
        staff_course_table = self.get_staff_course_table()
        # logging.info('user=%s, cid = %s' % (self.user, course_id))
        # logging.info('sct_user=%s' % staff_course_table['user'])
        if staff_course_table is None or not staff_course_table:
            return False
        if course_id and ((self.user, course_id) in staff_course_table['user_course']):
            return True
        if (course_id is None) and (self.user in staff_course_table['user']):
            return True
        
        for uent in staff_course_table['user'].get(self.user):
            if 'pm' in uent['role'].split(','):
                return True
            
        return False

    def dispatch(self):
        # Get a session store for this request.
        self.session_store = sessions.get_store(request=self.request)

        try:
            # Dispatch the request.
            webapp2.RequestHandler.dispatch(self)
        finally:
            # Save all sessions.
            self.session_store.save_sessions(self.response)

    @webapp2.cached_property
    def session(self):
        # Returns a session using the default cookie key.
        return self.session_store.get_session()

    def GoogleAuthenticate(self):
        user = users.get_current_user()
        if user:
            greeting = ('Welcome, %s! (<a href="%s">sign out</a>)' %
                        (user.nickname(), users.create_logout_url('/')))
        else:
            greeting = ('<a href="%s">Sign in or register</a>.' %
                        users.create_login_url('/'))
        logging.info(greeting)
        return user.nickname()

    def Authenticate(self):
        if 'google' in self.AUTH_METHOD:
            return self.GoogleAuthenticate()
        # If the request contains a login ticket, try to validate it
        ticket = self.request.get('ticket', None)
        if ticket is None and ('ticket' in self.session):
            ticket = self.session['ticket']
        if ticket is not None:
            if 'validated' in self.session:
                return self.session['validated']
            netid = self.Validate(ticket)
            logging.info('[Authenticate] ticket=%s, userid=%s' % (ticket, netid))
            if netid is not None:
                self.session['ticket'] = ticket
                self.session['validated'] = netid
                return netid
        return None

    def Validate(self, ticket):
        val_url = self.CAS_URL + "validate" + '?service=' + urllib.quote(self.ServiceURL()) + '&ticket=' + urllib.quote(ticket)
        r = urllib.urlopen(val_url).readlines()   # returns 2 lines
        logging.info('[validate] r=%s' % r)
        if len(r) == 2 and re.match("yes", r[0]) != None:
            return r[1].strip()
        return None

    def ServiceURL(self):
        ruri = self.request.uri
        if ruri:
            # ret = 'http://' + self.request.host + ruri
            ret = self.request.path_url
            ret = re.sub(r'ticket=[^&]*&?', '', ret)
            ret = re.sub(r'\?&?$|&$', '', ret)
            #ret = ret + '?' + self.request.query_string
            if self.request.get('auth', ''):
                self.session['auth_query'] = json.dumps(dict(self.request.GET.copy()))
            #if 'ticket' in qs:
            #    qs.pop('ticket')
            #ret = ret + '?' + urllib.urlencode(qs)
            logging.info('[ServiceURL] %s' % ret)
            return ret
            #$url = preg_replace('/ticket=[^&]*&?/', '', $url);
            #return preg_replace('/?&?$|&$/', '', $url);
        logging.info('[ServiceURL] no REQUEST_URI')
        return "something is badly wrong"

    def do_cas_redirect(self):
        if 'google' in self.AUTH_METHOD:
            return self.redirect("/login")
        login_url = self.CAS_URL + 'login' + '?service=' + urllib.quote(self.ServiceURL())
        logging.info('no auth, reditecting to %s' % login_url)
        return self.redirect(login_url)
        
    def sample_get_do_auth(self, msg=''):
        user = self.Authenticate()
        if user is None:
            return self.do_cas_redirect()

    def add_origin(self):
        origin = self.request.headers.get('Origin', None)
        if origin is None:
            self.response.headers.add_header("Access-Control-Allow-Origin", "*")
        else:
            self.response.headers['Access-Control-Allow-Origin'] = origin
        self.response.headers['Access-Control-Allow-Headers'] = 'Origin, X-Requested-With, Content-Type, Accept, X-CSRFToken'
        self.response.headers['Access-Control-Allow-Methods'] = 'POST, GET, PUT, DELETE'

