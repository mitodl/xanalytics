#
# custom report methods
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

class CustomReportPages(auth.AuthenticatedHandler, DataStats, DataSource):
    '''
    Methods for custom report pages
    '''

    @auth_and_role_required(role='pm')
    @auth_required
    def get_custom_report(self):
        '''
        custom reports page
        '''
        if not self.user in self.AUTHORIZED_USERS:	# require superuser
            return self.no_auth_sorry()

        data = self.common_data.copy()
        data.update({'is_staff': self.is_superuser(),
                     'reports': self.get_custom_report_metadata(single=False),
                 })
        template = JINJA_ENVIRONMENT.get_template('custom_reports.html')
        self.response.out.write(template.render(data))
        
    @auth_and_role_required(role='pm')
    @auth_required
    def edit_custom_report(self, report_name):
        '''
        edit custom report html, javascript, sql, description, ...
        '''
        if not self.user in self.AUTHORIZED_USERS:	# require superuser
            return self.no_auth_sorry()

        msg = ''
        if (self.request.POST.get('action')=='Save Changes'):
            fields = ['table_name', 'title', 'depends_on', 'html', 'sql', 'javascript', 'description']
            crm = self.get_custom_report_metadata(report_name)
            for field in fields:
                fval = self.request.POST.get(field)
                if fval is None:
                    logging.error("oops, expected value for field=%s, but got fval=%s" % (field, fval))
                else:
                    setattr(crm, field, fval)
            crm.put()
            logging.info('saved crm = %s' % crm)
            msg = "Saved custom report %s" % report_name

        crm = self.get_custom_report_metadata(report_name)

        data = {'html': crm.html,
                'js': crm.javascript,
                'report_name': report_name,
                'report': crm,
                'msg': msg,
        }
        data.update(self.common_data)

        template = JINJA_ENVIRONMENT.get_template('edit_custom_report.html')
        self.response.out.write(template.render(data))
        
    @auth_and_role_required(role='pm')
    @auth_required
    def ajax_get_report_html(self, report_name=None):
        '''
        return HTML for specified custom report
        '''
        if not self.user in self.AUTHORIZED_USERS:	# require superuser
            return self.no_auth_sorry()

        crm = self.get_custom_report_metadata(report_name)
        html = crm.html
        html += "<script type='text/javascript'>"
        html += "$(document).ready( function () {%s} );" % crm.javascript
        html += "</script>" 

        template = Template(html)

        render_data = {'report_name': report_name,
                       }

        data = {'html': template.render(render_data),
                'js': crm.javascript,
                }

        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))
        

    def get_custom_report_metadata(self, report_name=None, collection=None, single=True):
        '''
        return CustomReport ndb entry for report of specified name
        '''
        if collection and report_name:
            crq = CustomReport.query(CustomReport.name==report_name, CustomReport.collection==collection)
        elif report_name:
            crq = CustomReport.query(CustomReport.name==report_name)
        elif collection:
            crq = CustomReport.query(CustomReport.collection==collection)
        else:
            crq = CustomReport.query()
        if crq and single:
            return crq.fetch(1)[0]
        elif report_name and not crq:
            logging.error('No custom report found with name=%s' % report_name)
        return crq


    def find_latest_person_course_table(self, dataset):
        '''
        Return the table_id for the most recent person_course table in specified dataset
        '''
        pctable = ""
        pcdate = ""
        for table in bqutil.get_list_of_table_ids(dataset):
            if not table.startswith('person_course_'):
                continue
            m = re.search('person_course_.*_(20\d\d_\d\d_\d\d_[0-9]+)', table)
            if not m:
                continue
            tdate = m.group(1)
            if tdate > pcdate:
                pcdate = tdate
                pctable = table
        return pctable

    @auth_and_role_required(role='pm')
    @auth_required
    def ajax_get_report_data(self, report_name=None):
        '''
        get data for custom report.
        parameters like course_id, chapter_id, problem_id are passed in as GET or POST parameters
        '''
        if not self.user in self.AUTHORIZED_USERS:	# require superuser
            return self.no_auth_sorry()

        params = ['course_id', 'chapter_id', 'problem_id', 'draw', 'start', 'length', 'get_table_columns']
        pdata = {}
        for param in params:
            pdata[param] = self.request.POST.get(param, self.request.GET.get(param, None))
        course_id = pdata['course_id']

        # should re-authorize for course_id specific access here

        if course_id:
            dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.use_dataset_latest())
            pdata['person_course'] = '[%s.person_course]' % dataset
        else:
            dataset = self.get_course_report_dataset()
            # using course report dataset; list the tables, to determine which is the latest
            # person_course dataset, and use that for {person_course}
            pdata['person_course'] = '[%s.%s]' % (dataset, self.find_latest_person_course_table(dataset))

        # what table?  get custom course report configuration metadata for report name as specified
        crm = self.get_custom_report_metadata(report_name)
        table = crm.table_name

        # special handling for person_course table from particular dataset
        for m in re.findall('{person_course__([^ \}]+)}', crm.sql):
            org = m
            org_dataset = self.get_course_report_dataset(orgname=org)
            pcd = '[%s.%s]' % (org_dataset, self.find_latest_person_course_table(org_dataset))
            pdata['person_course__' + org] = pcd
            logging.info('[cr] org=%s, pc=%s.%s' % (org, org_dataset, pcd))

        logging.info("Using %s for custom report %s person_course" % (pdata['person_course'], report_name))

        # generate SQL and depends_on
        error = None
        sql = crm.sql.format(**pdata)
        def strip_brackets(x):
            x = x.strip()
            if x.startswith('[') and x.endswith(']'):
                x = x[1:-1]
                return x
            return x
        try:
            depends_on = [ strip_brackets(x.format(**pdata)) for x in (json.loads(crm.depends_on or "[]")) ]
        except Exception as err:
            logging.error("for course report %s, cannot process depends_on=%s" % (report_name, crm.depends_on))
            raise

        # get the data, and do query if needed

        logging.info('custom report get_report_data name=%s, table=%s.%s, depends_on=%s, pdata=%s' % (report_name, dataset, table, depends_on, pdata))

        try:
            bqdata = self.cached_get_bq_table(dataset, table, 
                                              sql=sql,
                                              depends_on=depends_on,
                                              startIndex=int(pdata['start'] or 0), 
                                              maxResults=int(pdata['length'] or 100000),
            )
            self.fix_bq_dates(bqdata)
        except Exception as err:
            bqdata = {'data': None}
            error = str(err)
            logging.error('custom report error %s' % error)
            raise

        tablecolumns = []
        if pdata['get_table_columns']:
            try:
                tableinfo = bqutil.get_bq_table_info(dataset, table)
            except Exception as err:
                error = (error or "\n") + str(err)
                tableinfo = None
                raise

            if tableinfo:
                fields = tableinfo['schema']['fields']
                field_names = [x['name'] for x in fields]
                tablecolumns = [ { 'data': x, 'title': x, 'class': 'dt-center' } for x in field_names ]

        data = self.common_data.copy()
        data.update({'data': bqdata['data'],
                     'draw': pdata['draw'],
                     'recordsTotal': bqdata.get('numRows', 0),
                     'recordsFiltered': bqdata.get('numRows', 0),
                     'error': error,
                     'tablecolumns': tablecolumns,
                 })
        
        
        # logging.info('[cr] data=%s' % data)

        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))
        


CustomReportRoutes = [
# displayed page routes
    webapp2.Route('/custom', handler=CustomReportPages, handler_method='get_custom_report'),
    webapp2.Route('/custom/edit_report/<report_name>', handler=CustomReportPages, handler_method='edit_custom_report'),

# ajax routes
    webapp2.Route('/custom/get_report_data/<report_name>', handler=CustomReportPages, handler_method='ajax_get_report_data'),
    webapp2.Route('/custom/get_report_html/<report_name>', handler=CustomReportPages, handler_method='ajax_get_report_html'),
]
