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
import hashlib

import jinja2

import gsdata
import bqutil
import auth
import traceback

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

    def custom_report_container(self, is_authorized_for_custom_report, **pdata):
        '''
        Return object which acts like a dict and can be used to generate HTML fragment as container for specified custom report.

        pdata = parameter data for custom report (also goes into authorization check)
        '''
        other = self
        class CRContainer(dict):
            def __init__(self, *args, **kwargs):
                self.immediate_view = False
                self.do_no_embed = False		# prevent report from rendering as embedded (need for custom_reports.html)
                self.force_embed = False
                super(CRContainer, self).__init__(*args, **kwargs)

            @property
            def immediate(self):
                self.immediate_view = True
                return self

            @property
            def embed(self):
                self.force_embed = True
                return self

            @property
            def no_embed(self):
                self.do_no_embed = True
                return self

            @property
            def parameter(self):
                crc = self
                class ParameterSetter(dict):
                    def __getitem__(self, parameter_name):
                        class ParameterValue(dict):
                            def __getitem__(self, parameter_value):
                                logging.info("CRContainer setting parameter %s = %s" % (parameter_name, parameter_value))
                                pdata[parameter_name] = parameter_value
                                return crc
                        return ParameterValue()
                return ParameterSetter()

            def __getitem__(self, report_name):
                try:
                    crm = other.get_custom_report_metadata(report_name)
                    err = None
                except Exception as err:
                    crm = None
                if not crm:
                    logging.info("No custom report '%s' found, err=%s" % (report_name, err))
                    return "Missing custom report %s" % report_name

                # check access authorization
                # logging.info('[crc] checking auth for report %s, pdata=%s' % (crm.name, pdata))
                auth_ok, msg = is_authorized_for_custom_report(crm, pdata)
                if not auth_ok:
                    return ""			# return empty string if not authorized

                # logging.info('[cr] name=%s, title=%s' % (crm.name, crm.title))	# debugging

                title = JINJA_ENVIRONMENT.from_string(crm.title)
                try:
                    title_rendered = title.render(pdata)
                except Exception as err:
                    logging.error('[cr] Failed to render report %s title %s' % (crm.name, crm.title))
                    title = crm.title

                parameters = {x:v for x,v in pdata.items() if v is not None}
                parameters['orgname'] = other.ORGNAME
                parameters['dashboard_mode'] = other.MODE	# 'mooc' or '' (empty meaning residential, non-mooc)
                parameters['course_report'] = other.get_course_report_dataset()
                parameters['course_report_org'] = other.get_course_report_dataset(force_use_org=True)
                parameters['orgname'] = other.ORGNAME
                
                if 'require_table' in (crm.meta_info or []):
                    table = crm.meta_info['require_table']
                    if '{' in table:
                        try:
                            table = table.format(**parameters)
                        except Exception as err:
                            logging.error("Cannot substitute for parameters in require_table=%s, err=%s" % (table, err))
                    if '.' in table:
                        (dataset, table) = table.split('.', 1)
                    else:
                        course_id = parameters.get('course_id')
                        if course_id:
                            try:
                                dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=other.use_dataset_latest())
                                tinfo = bqutil.get_bq_table_info(dataset, table)
                            except Exception as err:
                                if "Not Found" in str(err):
                                    logging.info("Suppressing report %s because %s.%s doesn't exist" % (title, dataset, table))
                                    return ""
                                logging.error(err)
                                logging.error(traceback.format_exc())
                                return ""

                report_id = hashlib.sha224("%s %s" % (crm.name, json.dumps(pdata))).hexdigest()
                if crm.description:
                    try:
                        crm.description = crm.description.format(**parameters)
                    except Exception as err:
                        logging.info('[cr] %s cannot format description %s' % (crm.name, crm.description))

                if self.do_no_embed and 'embedded' in (crm.meta_info or {}):
                    crm.meta_info.pop('embedded')
                if self.force_embed:
                    crm.meta_info['embedded'] = True

                template = JINJA_ENVIRONMENT.get_template('custom_report_container.html')
                data = {'is_staff': other.is_superuser(),
                        'report': crm,
                        'report_params': json.dumps(parameters),
                        'report_is_staff': pdata.get('staff'),
                        'report_meta_info': json.dumps(crm.meta_info or {}),
                        'immediate_view': json.dumps(self.immediate_view),
                        'do_embed' : (crm.meta_info or {}).get('embedded') or self.force_embed,
                        'title': title_rendered,
                        'id': report_id,
                }
                self.immediate_view = False	# return to non-immediate view by default
                self.do_no_embed = False		# return to default
                self.force_embed = False		# return to default
                return template.render(data)
        return CRContainer()
    
