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
import string
import random
import hashlib
import base64

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
                # return self.redirect('/custom/edit_report/%s' % name)
                #
                # because of how NDB may take awhile to store the new entry, we cannot go directly
                # to the report edit page, but instead, must go to a transition page asking 
                # for the user to click on a button first.
                data = self.common_data.copy()
                data.update({'report': crm,
                         })
                template = JINJA_ENVIRONMENT.get_template('edit_custom_report_transition.html')
                self.response.out.write(template.render(data))
                return

        elif (self.request.POST.get('action')=='Edit this report'):
            name =  self.request.POST.get('name')
            return self.redirect('/custom/edit_report/%s' % name)

        elif (self.request.POST.get('action')=='Upload Custom Report(s)'):
            report_file_data = self.request.get('file')
            overwrite = (self.request.get('overwrite')=='yes')
            msg += self.import_custom_report_from_file_data(report_file_data, overwrite)
                    
        cr_page_title = "Custom Reports"
        try:
            cr_page_title = local_config.CUSTOM_REPORTS_PAGE_TITLE
        except Exception as err:
            pass

        data = self.common_data.copy()
        data.update({'is_staff': self.is_superuser(),
                     'reports': self.get_custom_report_metadata(single=False),
                     'msg': msg,
                     'custom_report': self.custom_report_container(self.is_authorized_for_custom_report, staff=True,
                                                                   group_tag = "{{group_tag}}",
                                                               ),
                     'cr_page_title': cr_page_title,
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
                  'get_table_columns', 'force_query', 'sql_flags', "ignore_cache",
                  'group_tag', 'module_id']
        pdata = {}
        for param in params:
            # pdata[param] = self.request.POST.get(param, self.request.GET.get(param, None))
            pdata[param] = self.request.get(param, None)

        logging.info('[cr auth] report_name=%s, pdata=%s' % (report_name, pdata))

        auth_ok, msg2 = self.is_authorized_for_custom_report(crm, pdata)
        msg = msg + msg2

        return crm, pdata, auth_ok, msg

    def get_custom_report_library_javascript(self):
        '''
        Return javascript from custom report library.
        Allows frequenly used standard js to be centralized, to reduce clutter.
        '''
        class GetLibraryJS(dict):
            FILES = ["default", "plotting", "tables"]
            def __getitem__(self, filename):
                jsfn = "custom_report_%s.js" % filename
                jsdata, used_jsfn, uptodate = JINJA_ENVIRONMENT.loader.get_source(JINJA_ENVIRONMENT, jsfn)
                return jsdata
        return GetLibraryJS()

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

        if crm.meta_info.get('need_listings'):
            render_data['course_listings'] = self.get_course_listings()

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
                            'cr_js_library': self.get_custom_report_library_javascript(),
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
        if not parameter_values or parameter_values=="None":
            parameter_values = {}
        # self.session['edit_report_parameter_values'] = parameter_values

        editor_heights = self.request.POST.get('editor_heights')
        if editor_heights:
            self.session['editor_heights'] = editor_heights		# keep editor heights for session
        else:
            editor_heights = self.session.get('editor_heights')
        logging.info('[custom_reports] editor heights=%s' % editor_heights)

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

        # backward compatability: to accommodate jhints, ignore lines in javascript with jinja2 template commands
        if ('{{parameters}}' in crm.javascript) and not ('jshint ignore' in crm.javascript):
            newjs = []
            for k in crm.javascript.split('\n'):
                if (("{% autoescape" in k)) and not ('jshint ignore' in k):
                    k += "  // jshint ignore:line"
                elif ('{{parameters}}' in k) and not ('jshint ignore' in k):
                    newjs.append("/* jshint ignore:start */")
                    newjs.append(k)
                    k = "/* jshint ignore:end */"
                newjs.append(k)
            crm.javascript = '\n'.join(newjs)

        data = {'html': crm.html,
                'js': crm.javascript,
                'report_name': report_name,
                'report': crm,
                'msg': msg,
                'parameter_values': parameter_values,
                'meta_info': json.dumps(crm.meta_info),
                'editor_heights': editor_heights or "{}",
                'cr_js_library': self.get_custom_report_library_javascript(),
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

        parameters = {x:v for x,v in pdata.items() if v is not None}
        parameters['orgname'] = self.ORGNAME
        parameters['dashboard_mode'] = self.MODE	# 'mooc' or '' (empty meaning residential, non-mooc)

        uuid = ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(10))

        render_data = {'report_name': report_name,
                       'report_uuid': "%s_%s" % (report_name, uuid),
                       'orgname': self.ORGNAME,
                       'parameters': json.dumps(parameters),	# for js
                       'parameter_values': parameters,		# for html template variables
                       'custom_report': self.custom_report_container(self.is_authorized_for_custom_report, 
                                                                     **parameters),	# pass pdata so children of page also get parameters
                       'is_staff': self.is_superuser(),
                       'is_pm': self.is_pm(),
                       'cr_js_library': self.get_custom_report_library_javascript(),
                       }
        render_data.update(pdata)

        #html = crm.html
        html = JINJA_ENVIRONMENT.from_string(crm.html).render(render_data)	# allows custom reports to be included

        js_src = "<script type='text/javascript'>"
        js_src += "$(document).ready( function () {%s} );" % crm.javascript	# js goes in html
        js_src += "</script>" 

        try:
            js = Template(js_src).render(render_data)	# render template variables, ideally w/o global context
        except Exception as err:
            logging.info("Warning: could not render js in custom_reports, err=%s" % str(err))
            js = JINJA_ENVIRONMENT.from_string(js_src).render(render_data)
            
        #template = JINJA_ENVIRONMENT.from_string(html)

        # logging.info("get_report_html name=%s, parameters=%s" % (report_name, parameters))

        data = {'html': html + js,
                'js': crm.javascript,
                }

        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))
        

    def find_latest_person_course_table(self, dataset, project_id=None):
        '''
        Return the table_id for the most recent person_course table in specified dataset.
        Uses default project_id if one is not specified.
        '''
        pctable = ""
        pcdate = ""

        # project_id specified?
        optargs = {}
        if project_id:
            optargs['project_id'] = project_id

        for table in bqutil.get_list_of_table_ids(dataset, **optargs):
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
        {course_report} --> course_report_* dataset for the ORG or latest
        {course_report_org} --> course_report_ORG dataset for ORG = ORGANIZATION_NAME
        {orgname} --> organization name
        
        '''
        crm, pdata, auth_ok, msg = self.custom_report_auth_check(report_name)	# crm = CourseReport model
        if not auth_ok:
            return self.no_auth_sorry()
        course_id = pdata['course_id']
        force_query = pdata.get('force_query', False)
        if force_query == 'false':
            force_query = False
        ignore_cache = pdata.get('ignore_cache', False) or force_query

        # project_id specified?
        optargs = {}
        if 'project_id' in (crm.meta_info or {}):
            optargs['project_id'] = crm.meta_info['project_id']

        if course_id:
            dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.use_dataset_latest())
            pdata['person_course'] = '[%s.person_course]' % dataset
        elif 'dataset' in (crm.meta_info or {}):
            dataset = crm.meta_info['dataset']
        else:
            dataset = self.get_course_report_dataset()
            # using course report dataset; list the tables, to determine which is the latest
            # person_course dataset, and use that for {person_course}
            pdata['person_course_latest'] = self.find_latest_person_course_table(dataset, project_id=optargs.get('project_id'))
            pdata['person_course'] = '[%s.%s]' % (dataset, pdata['person_course_latest'])
        pdata['dataset'] = dataset
        pdata['course_report'] = self.get_course_report_dataset()
        pdata['course_report_org'] = self.get_course_report_dataset(force_use_org=True)
        pdata['orgname'] = self.ORGNAME
        pdata['sane_username'] = self.user.replace(' ', '_').replace('.', '_').replace('@', '_')

        if 'module_id' in pdata and pdata['module_id']:
            url_name = pdata['module_id'].rsplit('/',1)[-1]
            pdata['module_url_name'] = url_name.replace(':','__').replace('-','_')

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
        if not ('dataset' in (crm.meta_info or {})) and not table.startswith('stats_') and not (crm.meta_info.get('no_stats_ok')):
            table = "stats_" + table

        # special handling for person_course table from particular dataset
        for m in re.findall('{person_course__([^ \}]+)}', crm.sql):
            org = m
            org_dataset = self.get_course_report_dataset(orgname=org)
            pcd = '[%s.%s]' % (org_dataset, self.find_latest_person_course_table(org_dataset, project_id=optargs.get('project_id')))
            pdata['person_course__' + org] = pcd
            logging.info('[cr] org=%s, pc=%s.%s' % (org, org_dataset, pcd))

        # special handling for course_report tables for specific orgs
        for m in re.findall('{course_report__([^ \}]+)}', crm.sql):
            org = m
            org_dataset = self.get_course_report_dataset(orgname=org)
            pdata['course_report__' + org] = org_dataset

        logging.info("Using %s for custom report %s person_course" % (pdata.get('person_course'), report_name))

        error = None

        def setup_sql_flags():
            if 'sql_flags' in pdata:
                if not type(pdata['sql_flags'])==dict:
                    try:
                        pdata['sql_flags'] = json.loads(pdata['sql_flags'])
                    except Exception as err:
                        msg = "Cannot parse sql_flags as JSON!  sql_flags=%s" % pdata['sql_flags']
                        msg += err
                        logging.error(msg)
                        raise Exception(msg)

        # dynamic sql: the SQL is allowed to change based on input parameters
        # do this by treating the SQL as a jinja2 tempate
        if crm.meta_info.get('dynamic_sql'):
            setup_sql_flags()
            # a little sanity checking - disallow spaces in any sql_flags values
            sf = pdata['sql_flags']
            for k in sf:
                if ' ' in sf[k]:
                    msg = "Illegal sql_flags %s=%s!" % (k, sf[k])
                    msg += "sql_flags = %s" % json.dumps(sf, indent=4)
                    error = "<pre>%s</pre>" % (msg.replace('<','&lt;').replace('<','&gt;'))
                    data = {'error': error}
                    self.response.headers['Content-Type'] = 'application/json'   
                    self.response.out.write(json.dumps(data))
                    return

            try:
                sql_template = Template(crm.sql)
                sql = sql_template.render(pdata)
            except Exception as err:
                msg = 'Custom report data: failed to render dynamic SQL with pdata=%s, err=%s' % (pdata, err)
                logging.error(msg)
                logging.error('sql=%s' % crm.sql)
                error = "<pre>%s</pre>" % (msg.replace('<','&lt;').replace('<','&gt;'))
                data = {'error': error}
                self.response.headers['Content-Type'] = 'application/json'   
                self.response.out.write(json.dumps(data))
                return

            # append username to table name
            table = table + "_%s" % pdata['sane_username']

            force_query = True		# for now, all dynamic_sql is done with force_query
            ignore_cache = True
            the_sql = sql
        else:
            the_sql = crm.sql

        if 1:
            # generate SQL and depends_on
            try:
                sql = the_sql.format(**pdata)
            except Exception as err:
                msg = "Custom report data: failed to prepare SQL, err=%s" % str(err)
                msg += '\npdata = %s' %  pdata
                logging.error(msg)
                if self.is_superuser():
                    error = "<pre>%s</pre>" % (str(msg).replace('<','&lt;').replace('<','&gt;'))
                    data = {'error': error}
                    self.response.headers['Content-Type'] = 'application/json'   
                    self.response.out.write(json.dumps(data))
                    logging.error("Returning with error message")
                    return
                raise

        def strip_brackets(x):
            x = x.strip()
            if x.startswith('[') and x.endswith(']'):
                x = x[1:-1]
                return x
            return x

        if crm.meta_info.get('debug_sql'):
            msg = "debug_sql is true; not running SQL.  This is the SQL which would have been run:\n"
            msg += sql
            msg += "\n\nwith these parameters:\n"
            msg += json.dumps(pdata, indent=4)
            msg += "\n\nproducing the output table: %s.%s\n" % (dataset, table)
            error = "<pre>%s</pre>" % (msg.replace('<','&lt;').replace('<','&gt;'))
            data = {'error': error}
            self.response.headers['Content-Type'] = 'application/json'   
            self.response.out.write(json.dumps(data))
            return

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

        def output_error(err):
            error = "<pre>%s</pre>" % (str(err).replace('<','&lt;').replace('<','&gt;'))
            logging.error('custom report error %s' % error)
            logging.error(err)
            logging.error(traceback.format_exc())
            # raise
            if self.is_superuser():
                msg = ('\n'.join(the_msg))
                msg = msg.replace('<','&lt;').replace('<','&gt;')
                error += "<pre>%s</pre>" % msg
                error += "SQL: <pre>%s</pre>" % sql
                error += "Parameters: <pre>%s</pre>" % json.dumps(pdata, indent=4)
                error += "optargs: <pre>%s</pre>" % json.dumps(optargs, indent=4)
            data = {'error': error}
            self.response.headers['Content-Type'] = 'application/json'   
            self.response.out.write(json.dumps(data))

        # is the request "indexed", meaning only matching rows of the table are to be returned?
        indexed_column = crm.meta_info.get('indexed')
        if indexed_column:
            setup_sql_flags()
            indexed_value = pdata.get('sql_flags', {}).get('indexed_value')
            logging.info("[custom_reports] retrieving %s.%s with indexing on %s to match value %s" % (dataset, table, indexed_column, indexed_value))
            if not indexed_value:
                my_logger('Error: missing sql_flags.indexed_value to match indexed column %s in %s.%s' % (indexed_column, dataset, table))
                data = {'error': msg}
                self.response.headers['Content-Type'] = 'application/json'   
                self.response.out.write(json.dumps(data))
                return
            # ensure existence of indexed version of table.  By convention, that is a table named tablename + "__indexed_" + indexed_column
            # the table has a SHA1 hash of the indexed column added, and is sorted according to the last few characters
            # of the SHA1 hash.
            indexed_table = table + "__indexed_" + indexed_column
            indexing_sql_template = """select *,
                                  SUBSTR(TO_BASE64(SHA1({indexed_column})),-3,2) as index_sha1_2ch,
                                  ROW_NUMBER() over (order by index_sha1_2ch, username) as index_row_number{subnum},
                              from [{dataset}.{table}]
                              {where_clause}
                              order by index_sha1_2ch, {indexed_column}
                           """
            indexing_sql = indexing_sql_template.format(dataset=dataset, table=table, indexed_column=indexed_column, 
                                                        where_clause="",
                                                        subnum="")
            try:
                bqdata = self.cached_get_bq_table(dataset, indexed_table,
                                                  sql=indexing_sql,
                                                  logger=my_logger,
                                                  depends_on=["%s.%s" % (dataset, table)],
                                                  raise_exception=True,
                                                  ignore_cache=ignore_cache,
                                                  force_query=force_query,
                                                  startIndex=0,
                                                  maxResults=1,
                                                  **optargs
                                                )
            except Exception as err:
                if "Response too large to return" in str(the_msg):
                    # hmm - table too large!  can't workaround using allowLargeResult because the return results
                    # need to be ordered.  So let's break it up into multiple queries, appending each,
                    # by index_sha1_2ch
                    b64chars = "+/0123456789" + ''.join(map(chr,range(ord('A'), ord('Z')+1))) + ''.join(map(chr,range(ord('a'), ord('z')+1)))
                    # get table size, divide by 64M, to get number of divisions to use
                    tinfo = bqutil.get_bq_table_info(dataset, table, **optargs)
                    nbytes = int(tinfo['numBytes'])
                    ndivs = int(round(nbytes / (64*1024*1024)))
                    logging.info("Response too large - nbytes=%s, so trying ndivs=%s" % (nbytes, ndivs))
                    end_idx = None
                    start_idx = None
                    dn = int(64 / ndivs)
                    offset = dn
                    overwrite = True
                    nrows = 0
                    while (offset < 65):
                        start_idx = end_idx
                        last_row_index = nrows	# note ROW_NUMBER() starts with 1 (not zero)
                        if (offset < 64):
                            end_idx = b64chars[offset] + "+"
                        else:
                            end_idx = None	# boundary case
                        wc = "where "
                        if start_idx:
                            wc += '(SUBSTR(TO_BASE64(SHA1(%s)),-3,2) >= "%s") ' % (indexed_column, start_idx)
                        else:
                            wc += "True "
                        if end_idx:
                            wc += 'AND (SUBSTR(TO_BASE64(SHA1(%s)),-3,2) < "%s") ' % (indexed_column, end_idx)
                        logging.info("--> start_idx=%s, end_idx=%s, starting row %d" % (start_idx, end_idx, last_row_index))
                        tmp_sql = indexing_sql_template.format(dataset=dataset, table=table, indexed_column=indexed_column, 
                                                               where_clause=wc, subnum="_sub")
                        indexing_sql = "SELECT *, index_row_number_sub + %d as index_row_number FROM (%s)" % (last_row_index, tmp_sql)
                        try:
                            bqutil.create_bq_table(dataset, indexed_table,
                                                   sql=indexing_sql,
                                                   overwrite=overwrite,
                                                   logger=my_logger,
                                                   **optargs
                                               )
                            tinfo = bqutil.get_bq_table_info(dataset, indexed_table, **optargs)
                            nrows = int(tinfo['numRows'])
                            logging.info("--> Result from %s to %s has %d rows" % (start_idx, end_idx, nrows))
                        except Exception as err:
                            bqdata = {'data': None}
                            sql = indexing_sql
                            output_error(err)
                            return
                        overwrite = "append"
                        offset += dn
                        
                else:
                    bqdata = {'data': None}
                    sql = indexing_sql
                    output_error(err)
                    return

            # now ensure table index, and retrieve it.  It has just two columns: index_sha1_2ch, start_row
            tindex_table = table + "__index_for_" + indexed_column
            tindex_sql = """SELECT index_sha1_2ch, 
                                min(index_row_number) as start_row,
                                # max(index_row_number) as end_row,   # don't need this - just take next start_row
                            FROM [{dataset}.{indexed_table}]
                            group by index_sha1_2ch
                            order by index_sha1_2ch
                         """.format(dataset=dataset, indexed_table=indexed_table)
            try:
                bqdata = self.cached_get_bq_table(dataset, tindex_table,
                                                    sql=tindex_sql,
                                                    logger=my_logger,
                                                    depends_on=["%s.%s" % (dataset, indexed_table)],
                                                    raise_exception=True,
                                                    ignore_cache=ignore_cache,
                                                    force_query=force_query,
                                                    startIndex=0,
                                                    maxResults=10000,
                                                    **optargs
                                                )
            except Exception as err:
                bqdata = {'data': None}
                sql = tindex_sql
                output_error(err)
                return

            # find the start and end rows to retrieve, based the last characters of the SHA1 hash of the indexed value
            sha1_2ch = base64.b64encode(hashlib.sha1(indexed_value).digest())[-3:-1]
            start_row = None
            end_row = None
            for k in bqdata['data']:
                if start_row and not end_row:
                    end_row =  int(k['start_row'])
                if (k['index_sha1_2ch']==sha1_2ch):
                    start_row = int(k['start_row'])
            logging.info("Retrieving iv=%s, sha1_2ch=%s, rows %s to %s of %s.%s" % (indexed_value,
                                                                                    sha1_2ch,
                                                                                    start_row, end_row, dataset, indexed_table))
            if not start_row:
                output_error("Cannot find %s=%s in %s.%s" % (indexed_column, indexed_value,
                                                             dataset, indexed_table))
                bqdata = {'data': None}
                return
                
            max_results = (end_row or (start_row+4000)) - start_row
            bqdata = self.cached_get_bq_table(dataset, indexed_table, ignore_cache=True,
                                                startIndex=start_row-1,
                                                maxResults=max_results,
                                            )

            # extract just the row(s) with indexed_column value matching indexed_value (the hash is many to one)
            newdata = []
            for k in range(len(bqdata['data'])):
                datum = bqdata['data'][k]
                if (datum[indexed_column]==indexed_value):
                    newdata.append(datum)
            logging.info("--> Result has %d items, of which %d match" % (len(bqdata['data']), len(newdata)))
            bqdata['data'] = newdata                
            
            table = indexed_table	# so that columns are retrieved properly
            
        if not indexed_column:
            # retrieve full table
            try:
                bqdata = self.cached_get_bq_table(dataset, table, 
                                                  sql=sql,
                                                  logger=my_logger,
                                                  depends_on=depends_on,
                                                  startIndex=int(pdata['start'] or 0), 
                                                  maxResults=int(pdata['length'] or 100000),
                                                  raise_exception=True,
                                                  ignore_cache=ignore_cache,
                                                  force_query=force_query,
                                                  **optargs
                )
                self.fix_bq_dates(bqdata)
            except Exception as err:
                bqdata = {'data': None}
                output_error(err)
                return

        tablecolumns = []
        if pdata['get_table_columns']:
            try:
                tableinfo = bqutil.get_bq_table_info(dataset, table, **optargs)
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
                     'fields': bqdata['fields'],
                     'recordsTotal': bqdata.get('numRows', 0),
                     'recordsFiltered': bqdata.get('numRows', 0),
                     'error': error,
                     'tablecolumns': tablecolumns,
                     'output_table': table,
                     'output_dataset': dataset,
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
