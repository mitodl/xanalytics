#!/usr/bin/python
#
# File:   research.py
# Date:   16-Apr-15
# Author: I. Chuang <ichuang@mit.edu>
#
# MITx research dashboard for courses running on edx-platform.
# 
# Top-level module.

import logging
import os

import re
import json
import webapp2
import datetime

import gsdata
import bqutil
import auth
import local_config
import urllib

from unidecode import unidecode
from logger import GetRecentLogLines

from auth import auth_required
from stats import DataStats
from datatable import DataTableField
from datasource import DataSource
from dashboard import DashboardRoutes
from developer import DeveloperRoutes
from admin import AdminRoutes
from custom_reports import CustomReportRoutes, CustomReportPages
from reports import Reports
from collections import defaultdict, OrderedDict
from templates import JINJA_ENVIRONMENT

from google.appengine.api import memcache

config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': local_config.SESSION_SECRET_KEY,
}

ROUTES = [
    webapp2.Route('/', handler=CustomReportPages, handler_method='get_custom_report'),
]

ROUTES += AdminRoutes
ROUTES += CustomReportRoutes

application = webapp2.WSGIApplication(ROUTES, debug=True, config=config)
