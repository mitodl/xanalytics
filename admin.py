#
# admin page methods
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

from models import CustomReport
from collections import defaultdict, OrderedDict
from stats import DataStats
from datatable import DataTableField
from datasource import DataSource

from auth import auth_required, auth_and_role_required
from templates import JINJA_ENVIRONMENT

from google.appengine.api import memcache
mem = memcache.Client()

class AdminPages(auth.AuthenticatedHandler, DataStats, DataSource):
    '''
    Methods for admin pages
    '''

    @auth_required
    def get_admin(self):
        '''
        Admin page: show authorized users, clear cache
        '''
        if not self.user in self.AUTHORIZED_USERS:	# require superuser
            return self.no_auth_sorry()

        msg = ""
        action = self.request.POST.get('action', None)

        if action=='Flush cache':
            memcache.flush_all()
            msg = "Cache flushed"

        elif action=='Reload staff table':
            self.get_staff_table(reload=True)
            msg = "Staff table reloaded"

        elif action=='Reload course listings':
            self.get_course_listings(ignore_cache=True)
            msg = "Course listings reloaded"

        elif action=='Reload Course Listings':
            collection = self.request.POST.get('collection')
            self.get_course_listings(ignore_cache=True, collection=collection)
            msg = "Course listings for '%s' reloaded" % collection

        elif action=='Reload Custom Reports':
            collection = self.request.POST.get('collection')
            cnt = self.import_custom_report_metadata(ignore_cache=True, collection=collection)
            msg = "Custom Report Metadata for '%s' reloaded (%d reports)" % (collection, cnt)

        elif action=='Export Custom Reports':
            collection = self.request.POST.get('collection')
            cnt, destination = self.export_custom_report_metadata(ignore_cache=True, collection=collection)
            msg = "Custom Report Metadata for '%s' exported to %s (%d reports)" % (collection, destination, cnt)

        elif action=='Add staff':
            fields = ['username', 'role', 'course_id', 'notes']
            data = { x: (self.request.POST.get(x) or '') for x in fields }
            self.add_staff_table_entry(data)
            msg = "New staff %s added" % data

        todelete = self.request.POST.get('do-delete', None)
        if todelete is not None:
            self.disable_staff_table_entry(int(todelete))
            msg = "Deleted staff table row %s" % todelete

        stable = self.get_staff_table()

        stafftable = self.list2table([DataTableField({'icon':'delete', 'field': 'sid', 'title':' '}), 
                                      'username', 'role', 'course_id', 'notes'], stable)

        data = self.common_data.copy()
        course_listings_source = self.get_collection_metadata('COURSE_LISTINGS_TABLE')
        data.update({'superusers': self.AUTHORIZED_USERS,
                     'table': stafftable,
                     'msg': msg,
                     'listings_source': course_listings_source,
                     'staff_source': local_config.STAFF_COURSE_TABLE,
                     'collections': self.collections_available(asdict=True),
                 })
        template = JINJA_ENVIRONMENT.get_template('admin.html')
        self.response.out.write(template.render(data))

    @auth_required
    def ajax_log_entries(self):
        '''
        Return recent log entries
        '''
        if not self.user in self.AUTHORIZED_USERS:	# require superuser
            return self.no_auth_sorry()

        rll = GetRecentLogLines(100)
        self.response.headers['Content-Type'] = 'application/json'   
        def fix_dt(y):
            y['created'] = str(y['created'])[:19]
            return y
        loglines = [ fix_dt(x.to_dict()) for x in rll ]
        self.response.out.write(json.dumps({'loglines': loglines}))

AdminRoutes = [
    webapp2.Route('/admin', handler=AdminPages, handler_method='get_admin'),

    # ajax calls
    webapp2.Route('/get/LogEntries', handler=AdminPages, handler_method='ajax_log_entries'),
]
