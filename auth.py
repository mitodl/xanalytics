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

from pytz.gae import pytz
from webapp2_extras import sessions

from google.appengine.api import users
from google.appengine.ext import ndb
from google.appengine.ext import webapp
from google.appengine.ext.ndb import msgprop
from protorpc import messages 

#-----------------------------------------------------------------------------

class GeneralFunctions(object):

    @staticmethod
    def TheNow():
        tz = pytz.timezone('US/Eastern')
        n = datetime.datetime.utcnow().replace(tzinfo = pytz.utc)
        return n.astimezone(tz)

#-----------------------------------------------------------------------------

class AuthenticatedHandler(webapp2.RequestHandler, GeneralFunctions):
    CAS_URL = local_config.CAS_URL
    AUTH_METHOD = local_config.AUTH_METHOD

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

