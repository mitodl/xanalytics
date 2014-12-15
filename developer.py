#
# developer methods
#

import os
import csv
import codecs
import models
import datetime
import logging
import webapp2
import json

import jinja2

import gsdata
import bqutil
import auth

import local_config

from collections import defaultdict, OrderedDict
from stats import DataStats
from datatable import DataTableField
from datasource import DataSource

from auth import auth_required, auth_and_role_required
from templates import JINJA_ENVIRONMENT

# from google.appengine.api import memcache
# mem = memcache.Client()

class DeveloperPages(auth.AuthenticatedHandler, DataStats, DataSource):
    '''
    Methods for cross-course summary dashboard
    '''

    @auth_and_role_required(role='pm')
    @auth_required
    def get_developer(self):
        '''
        Dashboard page: show cross-course comparisons
        '''
        if not self.user in self.AUTHORIZED_USERS:	# require superuser
            return self.no_auth_sorry()

        data = self.common_data
        data.update({'is_staff': self.is_superuser(),
                 })
        template = JINJA_ENVIRONMENT.get_template('dev-editor.html')
        self.response.out.write(template.render(data))
        

DeveloperRoutes = [
# displayed page routes
    webapp2.Route('/developer', handler=DeveloperPages, handler_method='get_developer'),

# ajax routes
]
