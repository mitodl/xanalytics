#
# report methods
#

import os
import csv
import codecs
import models
import datetime
import logging
import webapp2
import json
import re

import jinja2

import gsdata
import bqutil
import auth

import local_config

from models import CustomReport
from jinja2 import Template
from collections import defaultdict, OrderedDict
from stats import DataStats
from datatable import DataTableField
from datasource import DataSource

from auth import auth_required, auth_and_role_required
from templates import JINJA_ENVIRONMENT

from google.appengine.api import memcache
mem = memcache.Client()

class Reports(object):
    '''
    This class is meant to be mixed-in
    '''

    def custom_report_container(self, **kwargs):
        '''
        Return object which acts like a dict and can be used to generate HTML fragment as container for specified custom report.
        '''
        other = self
        class CRContainer(dict):
            immediate_view = False

            @property
            def immediate(self):
                self.immediate_view = True
                return self

            def __getitem__(self, report_name):
                try:
                    crm = other.get_custom_report_metadata(report_name)
                    err = None
                except Exception as err:
                    crm = None
                if not crm:
                    logging.info("No custom report '%s' found, err=%s" % (report_name, err))
                    return "Missing custom report %s" % report_name
                template = JINJA_ENVIRONMENT.get_template('custom_report_container.html')
                data = {'is_staff': other.is_superuser(),
                        'report': crm,
                        'report_params': json.dumps(kwargs),
                        'report_is_staff': kwargs.get('staff'),
                        'report_meta_info': json.dumps(crm.meta_info),
                        'immediate_view': json.dumps(self.immediate_view),
                }
                return template.render(data)
        return CRContainer()
    
