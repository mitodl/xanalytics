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
import yaml
import re

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
from reports import Reports

from auth import auth_required, auth_and_role_required
from templates import JINJA_ENVIRONMENT

from google.appengine.api import memcache
mem = memcache.Client()

class CustomReportPages(auth.AuthenticatedHandler, DataStats, DataSource, Reports):
    '''
    Methods for custom report pages
    '''

    @auth_and_role_required(role='pm')
    @auth_required
    def get_custom_report(self, msg=""):
        '''
        custom reports page
        '''
        if not self.user in self.AUTHORIZED_USERS:	# require superuser
            return self.no_auth_sorry()

        if (self.request.POST.get('action')=='Create new Custom Report'):
            title = self.request.POST.get('title')
            name =  self.request.POST.get('name')
            existing_crm = self.get_custom_report_metadata(name, single=False)
            if existing_crm.count():
                msg = "Cannot create report '%s', already exists" % name
            else:
                crm = CustomReport(title=title, name=name)
                #crm.html = """<div id="contain-{{report_name}}" style="min-width: 310px; height: 400px; margin: 0 auto">
                crm.html = """<div id="contain-{{report_name}}" style="min-width: 310px; margin: 0 auto">
                               <img src="/images/loading_icon.gif"/>\n</div>"""
                jstemp, jsfn, uptodate = JINJA_ENVIRONMENT.loader.get_source(JINJA_ENVIRONMENT, 'custom_report_default.js')
                crm.javascript = str(jstemp)
                #jstemp = JINJA_ENVIRONMENT.get_template('custom_report_default.js')
                #crm.javascript = jstemp.render({})
                logging.info("[cr] creating new custom report %s" % crm)
                crm.put()
                return self.redirect('/custom/edit_report/%s' % name)

        elif (self.request.POST.get('action')=='Upload Custom Report(s)'):
            report_file_data = self.request.get('file')
            overwrite = (self.request.get('overwrite')=='yes')
            msg += self.import_custom_report_from_file_data(report_file_data, overwrite)
                    
        data = self.common_data.copy()
        data.update({'is_staff': self.is_superuser(),
                     'reports': self.get_custom_report_metadata(single=False),
                     'msg': msg,
                     'custom_report': self.custom_report_container(self.is_authorized_for_custom_report, staff=True,
                                                                   group_tag = "{{group_tag}}",
                                                               ),
                 })
        template = JINJA_ENVIRONMENT.get_template('custom_reports.html')
        self.response.out.write(template.render(data))
        

    def custom_report_auth_check(self, report_name):

        msg = ''

        try:
            crm = self.get_custom_report_metadata(report_name)
        except Exception as err:
            logging.error("[custom_report_auth_check] Cannot get custom report %s" % report_name)
            logging.error(err)
            msg = "Unknown custom report %s" % report_name
            auth_ok = False
            pdata = {}
            crm = None
            return crm, pdata, auth_ok, msg
        
        if not crm:
            msg = "Unknown custom report %s" % report_name
            auth_ok = True
            pdata = {}
            return crm, pdata, auth_ok, msg

        # params = ['course_id', 'chapter_id', 'problem_id', 'start', 'end']
        params = ['course_id', 'chapter_id', 'problem_id', 'draw', 'start', 'end', 'length', 
                  'get_table_columns', 'force_query',
                  'group_tag']
        pdata = {}
        for param in params:
            # pdata[param] = self.request.POST.get(param, self.request.GET.get(param, None))
            pdata[param] = self.request.get(param, None)

        logging.info('[cr auth] report_name=%s, pdata=%s' % (report_name, pdata))

        auth_ok, msg2 = self.is_authorized_for_custom_report(crm, pdata)
        msg = msg + msg2

        return crm, pdata, auth_ok, msg


    @auth_required
    def get_custom_report_page(self, report_name):
        '''
        Single custom report which behaves as a HTML page
        '''
        crm, pdata, auth_ok, msg = self.custom_report_auth_check(report_name)	# crm = CourseReport model
        if not auth_ok:
            return self.no_auth_sorry()

        if not crm:
            self.response.write(msg)
            return

        html = crm.html
        html += "<script type='text/javascript'>"
        html += "$(document).ready( function () {%s} );" % crm.javascript	# js goes in html, and thus gets template vars rendered
        html += "</script>" 

        template = JINJA_ENVIRONMENT.from_string(html)
        parameters = {x:v for x,v in pdata.items() if v is not None}

        render_data = self.common_data.copy()

        if crm.meta_info.get('need_tags'):
            render_data['course_tags'] = self.get_course_listings_tags()

        if ('course_id' in pdata) and pdata['course_id']:
            render_data['base'] = self.get_base(pdata['course_id'])
            logging.info('[page] base=%s' % render_data['base'])

        render_data.update({'report_name': report_name,
                            'parameters': json.dumps(parameters),	# for js
                            'parameter_values': parameters,		# for html template variables
                            'custom_report': self.custom_report_container(self.is_authorized_for_custom_report, 
                                                                          **pdata),	# pass pdata so children of page also get parameters
                            'is_staff': self.is_superuser(),
                            'is_pm': self.is_pm(),
                            'msg': msg,
                            'nav_is_active': self.nav_is_active(report_name),
                        })
        render_data.update(pdata)
        self.response.out.write(template.render(render_data))

        
    @auth_and_role_required(role='pm')
    @auth_required
    def edit_custom_report(self, report_name, crm=None):
        '''
        edit custom report html, javascript, sql, description, ...
        '''
        if not self.user in self.AUTHORIZED_USERS:	# require superuser
            return self.no_auth_sorry()

        parameter_values = self.session.get('edit_report_parameter_values')
        # self.session['edit_report_parameter_values'] = parameter_values

        msg = ''
        if (self.request.POST.get('action')=='Download Report'):

            try:
                data = self.export_custom_report_metadata(report_name=report_name, download=True)
                dump = yaml.dump(data, default_style="|", default_flow_style=False)
                # logging.info("custom report yaml=%s" % dump)
            except Exception as err:
                logging.error("Failed to find custom report named %s!" % report_name)
                raise
            self.response.headers['Content-Type'] = 'application/text'
            self.response.headers['Content-Disposition'] = 'attachment; filename=ANALYTICS_REPORT_%s.yaml' % report_name
            self.response.out.write(dump)
            return
            
        elif (self.request.POST.get('action')=='Download ALL Reports'):

            try:
                data = self.export_custom_report_metadata(report_name=None, download=True)
                dump = yaml.dump(data, default_style="|", default_flow_style=False)
                logging.info("custom report yaml=%s" % dump)
            except Exception as err:
                raise
            dtstr = self.TheNow().strftime('%Y-%m-%d_%H%M')
            self.response.headers['Content-Type'] = 'application/text'
            self.response.headers['Content-Disposition'] = 'attachment; filename=ANALYTICS_ALL_REPORTS_%s.yaml' % dtstr
            self.response.out.write(dump)
            return

        elif (self.request.POST.get('action')=='Delete Report'):
            try:
                crm = self.get_custom_report_metadata(report_name)
            except Exception as err:
                logging.error("Failed to find custom report named %s!" % report_name)
                raise
            crm.key.delete()
            msg = "Deleted course report %s" % report_name
            return self.get_custom_report(msg=msg)

        elif (self.request.POST.get('action')=='Save Changes'):
            fields = ['table_name', 'title', 'depends_on', 'html', 'sql', 'javascript', 'description', 'collection', 'group_tags', 'meta_info']
            try:
                crm = self.get_custom_report_metadata(report_name)
            except Exception as err:
                logging.error("Failed to find custom report named %s!" % report_name)
                raise
            for field in fields:
                fval = self.request.POST.get(field)
                if field=='group_tags':
                    fval = [x.strip() for x in fval.split(',')]
                elif field=='meta_info':
                    fval = eval(fval) or {}
                if fval is None:
                    logging.error("oops, expected value for field=%s, but got fval=%s" % (field, fval))
                else:
                    setattr(crm, field, fval)
            crm.put()
            logging.info('saved crm = %s' % crm)
            msg = "Saved custom report %s" % report_name

            if not crm.table_name:
                msg += "...Warning! table_name cannot be left empty"

        try:
            if not crm:
                crm = self.get_custom_report_metadata(report_name)
        except Exception as err:
            logging.error("Cannot get custom report %s" % report_name)
            raise

        data = {'html': crm.html,
                'js': crm.javascript,
                'report_name': report_name,
                'report': crm,
                'msg': msg,
                'parameter_values': parameter_values,
                'meta_info': json.dumps(crm.meta_info),
        }
        data.update(self.common_data)

        template = JINJA_ENVIRONMENT.get_template('edit_custom_report.html')
        self.response.out.write(template.render(data))
        
    @auth_and_role_required(role='pm')
    @auth_required
    def ajax_export_custom_report(self, report_name=None):
        '''
        export report metadata to source specified in config
        '''
        if not self.user in self.AUTHORIZED_USERS:	# require superuser
            return self.no_auth_sorry()

        cnt, destination = self.export_custom_report_metadata(report_name=report_name)
        msg = "Exported '%s' to %s (cnt=%s)" % (report_name, destination, cnt)
        data = {'msg': msg}
        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))

    @auth_required
    def ajax_get_report_html(self, report_name=None):
        '''
        return HTML for specified custom report
        '''
        crm, pdata, auth_ok, msg = self.custom_report_auth_check(report_name)	# crm = CourseReport model
        if not auth_ok:
            return self.no_auth_sorry()

        if self.request.get('save_parameters'):
            self.session['edit_report_parameter_values'] = json.dumps({x:v for x,v in pdata.items() if v is not None})
            logging.info("Saved edit_report_parameter_values = %s" % self.session['edit_report_parameter_values'])

        html = crm.html
        html += "<script type='text/javascript'>"
        html += "$(document).ready( function () {%s} );" % crm.javascript	# js goes in html, and thus gets template vars rendered
        html += "</script>" 

        template = Template(html)
        #template = JINJA_ENVIRONMENT.from_string(html)
        parameters = {x:v for x,v in pdata.items() if v is not None}

        render_data = {'report_name': report_name,
                       'parameters': json.dumps(parameters),	# for js
                       'parameter_values': parameters,		# for html template variables
                       'custom_report': self.custom_report_container(self.is_authorized_for_custom_report, 
                                                                     **parameters),	# pass pdata so children of page also get parameters
                       'is_staff': self.is_superuser(),
                       'is_pm': self.is_pm(),
                       }
        render_data.update(pdata)

        data = {'html': template.render(render_data),
                'js': crm.javascript,
                }

        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))
        

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

    @auth_required
    def ajax_get_report_data(self, report_name=None):
        '''
        do the actual call but in a try except to capture all errors, for reporting
        '''
        try:
            self.actual_ajax_get_report_data(report_name=report_name)
        except Exception as err:
            logging.error(err)
            logging.error(traceback.format_exc())
            data = self.common_data.copy()
            data.update({'data': None,
                         'error': str(err),
                         'tablecolumns': None,
                 })
            self.response.headers['Content-Type'] = 'application/json'   
            self.response.out.write(json.dumps(data))

    def actual_ajax_get_report_data(self, report_name=None):
        '''
        get data for custom report.
        parameters like course_id, chapter_id, problem_id are passed in as GET or POST parameters

        Defined parameters for SQL:

        {person_course} --> person_course table for the specific course
        {dataset} --> dataset for the specific course
        
        '''
        crm, pdata, auth_ok, msg = self.custom_report_auth_check(report_name)	# crm = CourseReport model
        if not auth_ok:
            return self.no_auth_sorry()
        course_id = pdata['course_id']
        force_query = pdata.get('force_query', False)
        if force_query == 'false':
            force_query = False

        if course_id:
            dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.use_dataset_latest())
            pdata['person_course'] = '[%s.person_course]' % dataset
        else:
            dataset = self.get_course_report_dataset()
            # using course report dataset; list the tables, to determine which is the latest
            # person_course dataset, and use that for {person_course}
            pdata['person_course'] = '[%s.%s]' % (dataset, self.find_latest_person_course_table(dataset))
        pdata['dataset'] = dataset

        # what table?  get custom course report configuration metadata for report name as specified
        table = crm.table_name
        if not table or table=="None":
            error = "No table name defined!  Cannot process this custom report"
            data = {'error': error}
            self.response.headers['Content-Type'] = 'application/json'   
            self.response.out.write(json.dumps(data))
            return
        if '{' in table:
            table = table.format(**pdata)
            table = table.replace('-', '_').replace(' ', '_')
        if not table.startswith('stats_'):
            table = "stats_" + table

        # special handling for person_course table from particular dataset
        for m in re.findall('{person_course__([^ \}]+)}', crm.sql):
            org = m
            org_dataset = self.get_course_report_dataset(orgname=org)
            pcd = '[%s.%s]' % (org_dataset, self.find_latest_person_course_table(org_dataset))
            pdata['person_course__' + org] = pcd
            logging.info('[cr] org=%s, pc=%s.%s' % (org, org_dataset, pcd))

        # special handling for course_report tables for specific orgs
        for m in re.findall('{course_report__([^ \}]+)}', crm.sql):
            org = m
            org_dataset = self.get_course_report_dataset(orgname=org)
            pdata['course_report__' + org] = org_dataset

        logging.info("Using %s for custom report %s person_course" % (pdata['person_course'], report_name))

        # generate SQL and depends_on
        error = None
        try:
            sql = crm.sql.format(**pdata)
        except Exception as err:
            logging.error("Custom report data: failed to prepare SQL, err=%s" % str(err))
            logging.error('pdata = %s' %  pdata)
            raise
        def strip_brackets(x):
            x = x.strip()
            if x.startswith('[') and x.endswith(']'):
                x = x[1:-1]
                return x
            return x

        try:
            if crm.depends_on and (not crm.depends_on=="None"):
                depends_on = [ strip_brackets(x.format(**pdata)) for x in (json.loads(crm.depends_on or "[]")) ]
            else:
                depends_on = None
        except Exception as err:
            logging.error("for course report %s, cannot process depends_on=%s" % (report_name, crm.depends_on))
            raise Exception("Bad format for the 'depends_on' setting in the custom report specification")
            raise

        # get the data, and do query if needed

        logging.info('custom report get_report_data name=%s, table=%s.%s, depends_on=%s, pdata=%s' % (report_name, dataset, table, depends_on, pdata))

        the_msg = []

        def my_logger(msg):
            logging.info(msg)
            the_msg.append(msg)

        try:
            bqdata = self.cached_get_bq_table(dataset, table, 
                                              sql=sql,
                                              logger=my_logger,
                                              depends_on=depends_on,
                                              startIndex=int(pdata['start'] or 0), 
                                              maxResults=int(pdata['length'] or 100000),
                                              raise_exception=True,
                                              ignore_cache=force_query,
                                              force_query=force_query,
            )
            self.fix_bq_dates(bqdata)
        except Exception as err:
            bqdata = {'data': None}
            error = str(err)
            logging.error('custom report error %s' % error)
            # raise
            if self.is_superuser():
                msg = ('\n'.join(the_msg))
                msg = msg.replace('<','&lt;')
                error += "<pre>%s</pre>" % msg
            data = {'error': error}
            self.response.headers['Content-Type'] = 'application/json'   
            self.response.out.write(json.dumps(data))
            return

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
    webapp2.Route('/page/<report_name>', handler=CustomReportPages, handler_method='get_custom_report_page'),

# ajax routes
    webapp2.Route('/custom/get_report_data/<report_name>', handler=CustomReportPages, handler_method='ajax_get_report_data'),
    webapp2.Route('/custom/get_report_html/<report_name>', handler=CustomReportPages, handler_method='ajax_get_report_html'),
    webapp2.Route('/custom/export_report/<report_name>', handler=CustomReportPages, handler_method='ajax_export_custom_report'),
]
