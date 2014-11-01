#!/usr/bin/python
#
# File:   main.py
# Date:   25-Oct-14
# Author: I. Chuang <ichuang@mit.edu>
#
# Analytics dashboard for courses running on edx-platform.
# 
# Top-level module.

import logging
import os

import re
import json
import webapp2
import datetime

import bqutil
import auth
import local_config

from collections import defaultdict, OrderedDict

import jinja2

# from gviz_data_table import encode
# from gviz_data_table import Table

from google.appengine.api import memcache
# from google.appengine.ext.webapp.template import render

mem = memcache.Client()

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class DataTableField(object):
    '''
    Info container for javascript datatable field labels and names.
    
    Initialize with field being a string (simple case), or a dict, with entries:

    field = data dict key for this data column
    title = title to display for data column (optional)
    width = percentage width for data column (optional)
    '''
    def __init__(self, field):
        if type(field)==DataTableField:
            field = field.field_in
        self.field_in = field
        if type(field)==dict:
            self.field = field['field']
            self.title = field.get('title', self.field)
            self.width = field.get('width', None)
            self.fmtclass = field.get('class', None)
        else:
            self.title = str(field)
            self.field = str(field)
            self.width = None
            self.fmtclass = None
    def __str__(self):
        return self.title
    def colinfo(self):
        ci = {'data': self.field}
        if self.fmtclass is not None:
            ci['className'] = self.fmtclass
        return ci

#-----------------------------------------------------------------------------

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

class MainPage(auth.AuthenticatedHandler):

    GSROOT = local_config.GOOGLE_STORAGE_ROOT
    ORGNAME = local_config.ORGANIZATION_NAME
    AUTHORIZED_USERS = local_config.STAFF_USERS
    MODE = local_config.MODE

    IM_WIDTH = 374/2
    IM_HEIGHT = 200/2
    bqdata = {}

    common_data = {'orgname': ORGNAME,
                   'mode': MODE,
    }

    def do_auth(self):
        user = self.Authenticate()
        self.user = user
        self.common_data['user'] = self.user
        if user is None:
            return self.do_cas_redirect
        return None

    def is_superuser(self):
        return self.user in self.AUTHORIZED_USERS        

    def is_user_authorized_for_course(self, course_id=None):
        staff_course_table = mem.get('staff_course_table')
        scdt = getattr(local_config, 'STAFF_COURSE_TABLE', None)
        if (not staff_course_table) and (scdt is not None) and (scdt):
            (dataset, table) = scdt.split('.')
            staff = self.cached_get_bq_table(dataset, table)['data']
            staff_course_table = {'user_course': {}, 'user': {}}
            for k in staff:
                staff_course_table['user_course'][(k['username'], k['course_id'])] = k
                staff_course_table['user']['username'] = k
            mem.set('staff_course_table', staff_course_table, time=3600*12)
            logging.info('staff_course_table = %s' % staff_course_table.keys())
        if staff_course_table and course_id and ((self.user, course_id) in staff_course_table['user_course']):
            return True
        if staff_course_table and (self.user in staff_course_table['user']):
            return True
        if self.is_superuser():
            return True
        return False

    def no_auth_sorry(self):
        self.response.write("Sorry, %s is not authorized to use this service" % self.user)

    def dict2table(self, names, data):
        '''
        Return HTML table with headers from names, and entries from data (which is a dict).
        '''
        def getent(x):
            return [x.get(name, None) for name in names]
        listdata = [getent(x) for x in data.values()]
        return self.list2table(names, listdata)

    @staticmethod
    def list2table(names, data, eformat=None, tid="table_id"):
        '''
        Return HTML table with headers from names, and entries from data.  

        names = list of strings
        data = list of lists 
        '''
        datatable = '''<table id="{tid}" class="display"><thead>  <tr> '''.format(tid=tid)
        for k in names:
            if hasattr(k, 'width') and k.width:
                fmt = 'width=%s' % k.width
            else:
                fmt = ''
            datatable += '<th {fmt}>{dat}</th>'.format(dat=k, fmt=fmt)
        datatable += '''</tr></thead>\n'''
        datatable += '''<tbody>\n'''
            
        def map_format(field, row):
            estr = (row.get(field, '') or '')
            if eformat is None:
                return estr
            elif name in eformat:
                return eformat[field](estr)
            return estr

        for k in data:
            datatable += '<tr>'
            if type(k) in [dict, OrderedDict, defaultdict]:
                row = [map_format(DataTableField(name).field, k) for name in names]
            else:
                row = k
            for ent in row:
                if type(ent) in [str, unicode]:
                    ent = ent.encode('utf8')
                datatable += '<td {fmt}>{dat}</td>'.format(dat=ent, fmt=fmt)
                # datatable += '<td>%s</td>' % ent
            datatable += '</tr>\n'
        datatable += '''</tbody></table>\n'''
        return datatable
            

    def _bq2geo(self, bqdata):
        # geodata output for region maps must be in the format region, value.
        # Assume the query output is in this format, get names from schema.
        logging.info(bqdata)
        table = Table()
        NameGeo = bqdata["schema"]["fields"][0]["name"]
        NameVal = bqdata["schema"]["fields"][1]["name"]
        table.add_column(NameGeo, unicode, NameGeo)
        table.add_column(NameVal, float, NameVal)
        for row in bqdata["rows"]:
            table.append(["US-"+row["f"][0]["v"], float(row["f"][1]["v"])])
        logging.info("FINAL GEODATA---")
        logging.info(table)
        return encode(table)
    # [END bq2geo]
    
    #-----------------------------------------------------------------------------

    def compute_sm_usage(self, course_id):
        '''
        Compute usage stats from studentmodule table for course
        '''
        dataset = bqutil.course_id2dataset(course_id)
        sql = """
                SELECT 
                    module_type, module_id, count(*) as ncount 
                FROM [{dataset}.studentmodule] 
                group by module_id, module_type
                order by module_id
        """.format(dataset=dataset)

        table = 'stats_module_usage'
        key = {'name': 'module_id'}
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key)

    def compute_problem_stats(self, course_id):
        '''
        Compute problem average grade, attempts
        '''
        dataset = bqutil.course_id2dataset(course_id)
        sql = """
                SELECT '{course_id}' as course_id,
                    PA.problem_url_name as url_name,
                    avg(PA.attempts) as avg_attempts,
                    avg(PA.grade) as avg_grade,
                    max(PA.max_grade) as max_max_grade,
                    max(PA.grade) as emperical_max_grade,
                    count(*) as nsubmissions,
                    min(PA.created) as first_date,
                    max(PA.created) as last_date,
                    max(PA.attempts) as max_attempts,
                    sum(case when integer(10*PA.grade/PA.max_grade)=0 then 1 else 0 end) as grade_hist_bin0,
                    sum(case when integer(10*PA.grade/PA.max_grade)=1 then 1 else 0 end) as grade_hist_bin1,
                    sum(case when integer(10*PA.grade/PA.max_grade)=2 then 1 else 0 end) as grade_hist_bin2,
                    sum(case when integer(10*PA.grade/PA.max_grade)=3 then 1 else 0 end) as grade_hist_bin3,
                    sum(case when integer(10*PA.grade/PA.max_grade)=4 then 1 else 0 end) as grade_hist_bin4,
                    sum(case when integer(10*PA.grade/PA.max_grade)=5 then 1 else 0 end) as grade_hist_bin5,
                    sum(case when integer(10*PA.grade/PA.max_grade)=6 then 1 else 0 end) as grade_hist_bin6,
                    sum(case when integer(10*PA.grade/PA.max_grade)=7 then 1 else 0 end) as grade_hist_bin7,
                    sum(case when integer(10*PA.grade/PA.max_grade)=8 then 1 else 0 end) as grade_hist_bin8,
                    sum(case when integer(10*PA.grade/PA.max_grade)=9 then 1 else 0 end) as grade_hist_bin9,
                    sum(case when integer(10*PA.grade/PA.max_grade)=10 then 1 else 0 end) as grade_hist_bin10,
                    sum(case when integer(10*PA.attempts/M.max_attempts)=0 then 1 else 0 end) as attempts_hist_bin0,
                    sum(case when integer(10*PA.attempts/M.max_attempts)=1 then 1 else 0 end) as attempts_hist_bin1,
                    sum(case when integer(10*PA.attempts/M.max_attempts)=2 then 1 else 0 end) as attempts_hist_bin2,
                    sum(case when integer(10*PA.attempts/M.max_attempts)=3 then 1 else 0 end) as attempts_hist_bin3,
                    sum(case when integer(10*PA.attempts/M.max_attempts)=4 then 1 else 0 end) as attempts_hist_bin4,
                    sum(case when integer(10*PA.attempts/M.max_attempts)=5 then 1 else 0 end) as attempts_hist_bin5,
                    sum(case when integer(10*PA.attempts/M.max_attempts)=6 then 1 else 0 end) as attempts_hist_bin6,
                    sum(case when integer(10*PA.attempts/M.max_attempts)=7 then 1 else 0 end) as attempts_hist_bin7,
                    sum(case when integer(10*PA.attempts/M.max_attempts)=8 then 1 else 0 end) as attempts_hist_bin8,
                    sum(case when integer(10*PA.attempts/M.max_attempts)=9 then 1 else 0 end) as attempts_hist_bin9,
                    sum(case when integer(10*PA.attempts/M.max_attempts)=10 then 1 else 0 end) as attempts_hist_bin10,
                FROM [{dataset}.problem_analysis] PA
                JOIN 
                    (SELECT problem_url_name as url_name, 
                            max(attempts) as max_attempts 
                     FROM [{dataset}.problem_analysis]
                     group by url_name) as M
                ON PA.problem_url_name = M.url_name
                group by url_name, problem_url_name
                order by problem_url_name
        """.format(dataset=dataset, course_id=course_id)

        table = 'stats_for_problems'
        key = {'name': 'url_name'}
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key)


    def compute_usage_stats(self, course_id):
        '''
        Compute usage stats, i.e. # registered, viewed, explored, based on person-course
        '''
        dataset = bqutil.course_id2dataset(course_id)
        sql = """
           SELECT course_id,
                   count(*) as registered_sum,
                   sum(case when viewed then 1 else 0 end) as viewed_sum,
                   sum(case when explored then 1 else 0 end) as explored_sum,
                   sum(case when certified then 1 else 0 end) as certified_sum,
    
                   sum(case when gender='m' then 1 else 0 end) as n_male,
                   sum(case when gender='f' then 1 else 0 end) as n_female,
    
                   sum(case when mode="verified" then 1 else 0 end) as n_verified_id,
                   sum(case when (viewed and mode="verified") then 1 else 0 end) as verified_viewed,
                   sum(case when (explored and mode="verified") then 1 else 0 end) as verified_explored,
                   sum(case when (certified and mode="verified") then 1 else 0 end) as verified_certified,
                   avg(case when (mode="verified") then grade else null end) as verified_avg_grade,
    
                   sum(case when (gender='m' and mode="verified") then 1 else 0 end) as verified_n_male,
                   sum(case when (gender='f' and mode="verified") then 1 else 0 end) as verified_n_female,
    
                   sum(nplay_video) as nplay_video_sum,
                   avg(nchapters) as nchapters_avg,
                   sum(ndays_act) as ndays_act_sum,
                   sum(nevents) as nevents_sum,
                   sum(nforum_posts) as nforum_posts_sum,
                   min(case when certified then grade else null end) as min_gade_certified,
                   min(start_time) as min_start_time,
                   max(last_event) as max_last_event,
                   max(nchapters) as max_nchapters,
                   sum(nforum_votes) as nforum_votes_sum,
                   sum(nforum_endorsed) as nforum_endorsed_sum,
                   sum(nforum_threads) as nforum_threads_sum,
                   sum(nforum_comments) as nforum_commments_sum,
                   sum(nforum_pinned) as nforum_pinned_sum,
    
                   avg(nprogcheck) as nprogcheck_avg,
                   avg(case when certified then nprogcheck else null end) as certified_nprogcheck,
                   avg(case when (mode="verified") then nprogcheck else null end) as verified_nprogcheck,
    
                   sum(nshow_answer) as nshow_answer_sum,
                   sum(nseq_goto) as nseq_goto_sum,
                   sum(npause_video) as npause_video_sum,
                   avg(avg_dt) as avg_of_avg_dt,
                   avg(sum_dt) as avg_of_sum_dt,
                   avg(case when certified then avg_dt else null end) as certified_avg_dt,
                   avg(case when certified then sum_dt else null end) as certified_sum_dt,
                   sum(case when (ip is not null) then 1 else 0 end) as n_have_ip,
                   sum(case when ((ip is not null) and (cc_by_ip is null)) then 1 else 0 end) as n_missing_cc,
                FROM [{dataset}.person_course] 
                group by course_id
        """.format(dataset=dataset, course_id=course_id)

        table = 'stats_overall'
        key = None
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key)


    def cached_get_bq_table(self, dataset, table, sql=None, key=None, drop=None):
        '''
        Get a dataset from BigQuery; use memcache
        '''
        memset = '%s.%s' % (dataset,table)
        data = mem.get(memset)
        if not data:
            data = bqutil.get_bq_table(dataset, table, sql, key=key)
            if (drop is not None) and drop:
                for key in drop:
                    data.pop(key)	# because data can be too huge for memcache ("Values may not be more than 1000000 bytes in length")
            try:
                mem.set(memset, data, time=3600*12)
            except Exception as err:
                logging.error('error doing mem.set for %s.%s from bigquery' % (dataset, table))
        self.bqdata[table] = data
        return data

    #-----------------------------------------------------------------------------

    @auth_required
    def get_main(self):
        '''
        Main page: show list of all courses
        '''
        data = None
        if not data:
            dataset = 'courses'
            table = 'listings'
            courses = self.cached_get_bq_table(dataset, table)

            # logging.info('course listings: %s' % courses['data'])

            for k in courses['data']:
                cid = k['course_id']
                if not cid:
                    logging.error('oops, bad course_id! line=%s' % k)
                    continue
                k['course_image'] = self.get_course_image(cid)

            html = self.list2table(map(DataTableField, 
                                       [{'field': 'semester', 'title':'Semester'},
                                        {'field': 'course_number', 'title': 'Course #'}, 
                                        {'field': 'course_image', 'title': 'Course image'}, 
                                        {'field': 'title', 'title': 'Course Title'},
                                        'course_id',
                                       ]), 
                                   courses['data'])

            data = self.common_data
            data.update({'data': {},
                         'table': html,
                     })
        template = JINJA_ENVIRONMENT.get_template('courses.html')
        # template = os.path.join(os.path.dirname(__file__), 'courses.html')
        self.response.out.write(template.render(data))

    def get_course_image(self, course_id):
        #  images 374x200
        cdir = course_id.replace('/','__')
        img = '<img width="{width}" height="{height}" src="https://storage.googleapis.com/{gsroot}/{cdir}/course_image.jpg"/>'.format(gsroot=self.GSROOT,
                                                                                                                                        cdir=cdir,
                                                                                                                                        width=self.IM_WIDTH,
                                                                                                                                        height=self.IM_HEIGHT,)
        return img


    def load_course_axis(self, course_id):
        '''
        Get course axis table from BQ.  Use memcache.

        The course axis has these fields:

        category, index, url_name, name, gformat, due, start, module_id, course_id, path, data.ytid, data.weight, chapter_mid
        '''
        dataset = bqutil.course_id2dataset(course_id)
        table = "course_axis"
        key={'name': 'url_name'}
        return self.cached_get_bq_table(dataset, table, key=key, drop=['data'])['data_by_key']


    def load_person_course(self, course_id):
        '''
        Get person_course table from BQ.  Use memcache.

        The person_course table has these relevant fields (among many):

        username, viewed, explored, ip
        '''
        dataset = bqutil.course_id2dataset(course_id)
        table = "person_course"
        key = None
        return self.cached_get_bq_table(dataset, table)

    def get_sm_nuser_views(self, module_id):
        return self.bqdata['stats_module_usage']['data_by_key'].get('i4x://' + module_id, {}).get('ncount', '')

    def get_base(self, course_id):
        '''
        Return base url (e.g. edx.org) for access to given course_id
        '''
        csm = getattr(local_config, 'COURSE_SITE_MAP', None)
        if csm is not None and csm:
            for key, val in csm.iteritems():
                if re.match(val['match'], course_id):
                    return val['url']
        return local_config.DEFAULT_COURSE_SITE

    @auth_required
    def ajax_get_usage_stats(self, org=None, number=None, semester=None):

        course_id = '/'.join([org, number, semester])
        usdat = self.compute_usage_stats(course_id)['data'][0]
        # categories = ['registered', 'viewed', 'explored']
        data = {'data': [usdat] }

        logging.info('ajax_get_usage_stats data=%s' % data)

        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))
        
        
    def setup_module_info(self, org=None, number=None, semester=None, url_name=None):
        '''
        setup common module info for problem, video, html
        '''
        course_id = '/'.join([org, number, semester])
        caxis = self.load_course_axis(course_id)

        # get problem info
        the_module = caxis[url_name]
        module_id = the_module['module_id']
        chapter_mid = the_module['chapter_mid']
        chapter_url_name = chapter_mid.rsplit('/',1)[-1]
        name = the_module['name']

        data = self.common_data
        data.update({'course_id': course_id,
                     'name': name,
                     'chapter_mid': chapter_mid,
                     'cun': chapter_url_name,
                     'base': self.get_base(course_id),
                     'url_name': url_name,
                     'module_id': module_id,
                     'module': the_module,
                     'caxis': caxis,
                 })
        return data

    @auth_required
    def get_problem(self, **kwargs):
        '''
        single problem analytics view

        - iframe
        '''

        data = self.setup_module_info(**kwargs)
        # template = os.path.join(os.path.dirname(__file__), 'problem.html')
        template = JINJA_ENVIRONMENT.get_template('problem.html')
        self.response.out.write(template.render(data))


    @auth_required
    def ajax_get_problem_stats(self, org=None, number=None, semester=None, problem_url_name=None):

        course_id = '/'.join([org, number, semester])

        ps = self.compute_problem_stats(course_id)
        # logging.info('problem url_name = %s' % problem_url_name)
        pstats = ps['data_by_key'][problem_url_name]
        # logging.info('pstats = %s' % pstats)

        data = {'data': [ pstats ] }

        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))


    @auth_required
    def get_html(self, **kwargs):
        '''
        single html analytics view

        - iframe
        '''
        data = self.setup_module_info(**kwargs)
        template = JINJA_ENVIRONMENT.get_template('html_page.html')
        self.response.out.write(template.render(data))

        
    @auth_required
    def get_video(self, **kwargs):
        '''
        single video analytics view

        - iframe
        '''
        data = self.setup_module_info(**kwargs)
        template = JINJA_ENVIRONMENT.get_template('video.html')
        self.response.out.write(template.render(data))
        
    @auth_required
    def get_chapter(self, org=None, number=None, semester=None, url_name=None):
        '''
        single chapter analytics view

        - sequentials and problems
        '''
        course_id = '/'.join([org, number, semester])
        caxis = self.load_course_axis(course_id)

        # get chapter info
        the_chapter = caxis[url_name]
        chapter_mid = the_chapter['module_id']
        chapter_name = the_chapter['name']

        # get module usage counts
        self.compute_sm_usage(course_id)

        # get chapter contents
        ccontents = [x for x in caxis.values() if (x['chapter_mid']==chapter_mid) and (not x['category']=='vertical')]
        
        # problem stats
        ps = self.compute_problem_stats(course_id)
        pstats = ps['data_by_key']

        # add nuser_views
        for caent in ccontents:
            caent['nuser_views'] = self.get_sm_nuser_views(caent['module_id'])
            caent['avg_grade'] = ''
            caent['max_grade'] = ''
            caent['avg_attempts'] = ''
            caent['max_attempts'] = ''
            caent['nsubmissions'] = ''
            if caent['category']=='problem':
                ps = pstats.get(caent['url_name'], None)
                if ps is not None:
                    caent['avg_grade'] = '%6.2f' % float(ps['avg_grade'])
                    caent['max_grade'] = '%6.2f' % float(ps['max_max_grade'])
                    caent['avg_attempts'] = '%6.2f'% float(ps['avg_attempts'])
                    caent['max_attempts'] = ps['max_attempts']
                    caent['nsubmissions'] = ps['nsubmissions']

        fields = [ DataTableField(x) for x  in [{'field': 'index', 'title': 'Time index', 'width': '8%', 'class': 'dt-center'}, 
                                                {'field': 'category', 'title': "Module category", 'width': '10%'},
                                                {'field': 'name', 'title': "Module name"},
                                                {'field': 'nsubmissions', 'title': "# submissions", 'width': '7%', 'class': 'dt-center'},
                                                {'field': 'avg_grade', 'title': "AVG grade", 'width': '7%', 'class': 'dt-center'},
                                                {'field': 'max_grade', 'title': "MAX grade", 'width': '7%', 'class': 'dt-center'},
                                                {'field': 'avg_attempts', 'title': "AVG attempts", 'width': '7%', 'class': 'dt-center'},
                                                {'field': 'max_attempts', 'title': "MAX attempts", 'width': '7%', 'class': 'dt-center'},
                                                {'field': 'start', 'title': "Start date", 'width': '12%', 'class': 'dt-center'},
                                                {'field': 'nuser_views', 'title': '# user views', 'width': '7%', 'class': 'dt-center'},
                                                # {'field': 'url_name', 'title': 'url_name'},
                                               ] ]

        def makelink(txt, rdat):
            try:
                link = "<a href='/{category}/{course_id}/{url_name}'>{txt}</a>".format(txt=txt.encode('utf8'),
                                                                                       course_id=course_id,
                                                                                       category=rdat['category'],
                                                                                       url_name=rdat['url_name'])
            except Exception as err:
                logging.error('oops, cannot make link for %s' % repr(rdat))
                link = txt

            p = {'base': self.get_base(course_id),
                 'course_id': course_id,
                 'cmid': url_name,
                 'url_name': rdat['url_name'],
                 }

            # cases for url base 

            link += "<span style='float:right'><a href='{base}/courses/{course_id}/jump_to_id/{url_name}'><img src=/images/link-small.png></a></span>".format(**p)
            return link
            
        def makerow(rdat):
            row = rdat
            row['start'] = self.fix_date(rdat['start'])
            if row['category'] in ['problem', 'video', 'html']:
                row['name'] = makelink(row['name'], rdat)
            return row

        tablehtml = self.list2table(fields, [])
        tabledata = json.dumps([ makerow(x) for x in ccontents ])
        tablefields = json.dumps([x.colinfo() for x in fields])

        data = self.common_data
        data.update({'tabledata': tabledata,
                     'fields': tablefields,
                     'table': tablehtml,
                     'course_id': course_id,
                     'chapter_name': chapter_name,
                 })

        template = JINJA_ENVIRONMENT.get_template('chapter.html')
        self.response.out.write(template.render(data))
        

    @staticmethod
    def fix_date(x):
        if x:
            return str(datetime.datetime.utcfromtimestamp(float(x)))
        return ''

    @auth_required
    def get_course(self, org=None, number=None, semester=None):
        '''
        single course analytics view

        - overall statistics (number of components of various categories)
        - show table of chapters
        '''
        course_id = '/'.join([org, number, semester])
        caxis = self.load_course_axis(course_id)

        # get module usage counts
        self.compute_sm_usage(course_id)
                
        # overall content stats
        counts = defaultdict(int)
        counts_by_chapter = defaultdict(lambda: defaultdict(int))
        sequentials_by_chapter = defaultdict(list)
        for index, caent in caxis.iteritems():
            if caent['category'] in ['course']:
                continue
            counts[caent['category']] += 1
            if 'chapter_mid' in caent:
                counts_by_chapter[caent['chapter_mid']][caent['category']] += 1
                if caent['category']=='sequential':
                    caent['nuser_views'] = self.get_sm_nuser_views(caent['module_id'])
                    sequentials_by_chapter[caent['chapter_mid']].append(caent)

        stats_fields = counts.keys()
        # stats_fields = [ DataTableField({'field': x, 'class': 'dt-center'}) for x in stats_fields]
        stats_table = self.list2table(stats_fields, [counts], tid="stats_table")

        def makelink(txt, rdat):
            return "<a href='/chapter/{course_id}/{url_name}'>{txt}</a>".format(txt=txt,
                                                                                course_id=course_id,
                                                                                url_name=rdat['url_name'])

        # show table with just chapters, and present sequentials as extra information when clicked
        fields = [ DataTableField(x) for x  in [{'field': 'index', 'title': 'Time index', 'width': '8%', 'class': 'dt-center'}, 
                                                {'field': 'name', 'title': "Chapter name"},
                                                {'field': 'start', 'title': "Start date", 'width': '18%'},
                                                {'field': 'nuser_views', 'title': '# user-views', 'width': '10%', 'class': 'dt-center'},
                                               ] ]
        def makerow(rdat):
            # row = [rdat['index'], makelink(rdat['name'], rdat), fix_date(rdat['start'])]
            #row = {'index': rdat['index'], 'name': makelink(rdat['name'], rdat), 'start': fix_date(rdat['start'])}
            row = rdat
            chapter_mid = rdat['module_id']
            row['name'] = makelink(rdat['name'], rdat)
            row['start'] = self.fix_date(rdat['start'])
            row['n_sequential'] = counts_by_chapter[chapter_mid]['sequential']
            row['n_html'] = counts_by_chapter[chapter_mid]['html']
            row['n_problem'] = counts_by_chapter[chapter_mid]['problem']
            row['n_video'] = counts_by_chapter[chapter_mid]['video']
            row['sequentials'] = json.dumps(sequentials_by_chapter[chapter_mid])
            row['nuser_views'] = self.get_sm_nuser_views(chapter_mid)
            return row

        # logging.info('sm_usage:')
        # logging.info(self.bqdata['stats_module_usage']['data_by_key'])

        tablehtml = self.list2table([' '] + fields, [])
        tabledata = json.dumps([ makerow(x) for x in caxis.values() if x['category']=='chapter'])
        tablefields = json.dumps([
            {
                "class":          'details-control',
                "orderable":      False,
                "data":           None,
                'width': '5%',
                "defaultContent": ''
            },] +  [x.colinfo() for x in fields])

        data = self.common_data
        data.update({'tabledata': tabledata,
                     'course_id': course_id,
                     'fields': tablefields,
                     'table': tablehtml,
                     'stats_table': stats_table,
                     'stats_columns': json.dumps([ {'className': 'dt-center'}] *len(stats_fields)),
                     'image': self.get_course_image(course_id),
                 })
        
        template = JINJA_ENVIRONMENT.get_template('one_course.html')
        self.response.out.write(template.render(data))
        
    @auth_required
    def get_axis(self, org=None, number=None, semester=None):
        '''
        show full course axis -- mainly for debugging
        '''
        course_id = '/'.join([org, number, semester])
        caxis = self.load_course_axis(course_id)

        if 1:
            tablehtml = self.list2table(['category', 'index', 'url_name', 'name', 'gformat', 'due', 'start', 
                                         'module_id', 'path', 'data_ytid', 'data_weight', 'chapter_mid'],
                                        caxis.values(),
                                        eformat={'due': self.fix_date, 'start': self.fix_date}, )

        data = self.common_data
        data.update({'course_id': course_id,
                     'table': tablehtml,
                 })
        
        template = JINJA_ENVIRONMENT.get_template('course_axis.html')
        self.response.out.write(template.render(data))
        

    def fix_bq_dates(self, table):
        '''
        Using schema information, fix TIMESTAMP fields to display as dates.
        '''
        def map_field(idx, name):
            logging.info('Fixing timestamp for field %s' % name)
            for row in table['data']:
                # logging.info('row=%s' % row)
                if name in row and row[name]:
                    row[name] = str(datetime.datetime.utcfromtimestamp(float(row[name])))

        for k in range(0, len(table['fields'])):
            field = table['fields'][k]
            if field['type']=='TIMESTAMP':
                map_field(k, field['name'])


    @auth_required
    def get_table(self, dataset=None, table=None, org=None, number=None,semester=None):
        '''
        show arbitrary table from bigquery -- mainly for debugging
        '''
        if dataset is None:
            course_id = '/'.join([org, number, semester])
            dataset = bqutil.course_id2dataset(course_id)
            if not self.is_user_authorized_for_course(course_id):
                return self.no_auth_sorry()
        else:
            course_id = None
            if not self.user in self.AUTHORIZED_USERS:
                return self.no_auth_sorry()

        bqdata = bqutil.get_table_data(dataset, table)
        self.fix_bq_dates(bqdata)

        tablehtml = self.list2table(bqdata['field_names'],
                                    bqdata['data'])

        data = self.common_data
        data.update({'dataset': dataset,
                     'table': table,
                     'tablehtml': tablehtml,
                 })
        
        template = JINJA_ENVIRONMENT.get_template('show_table.html')
        self.response.out.write(template.render(data))

config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': 'dkjasf912lkj8d09',
}

application = webapp2.WSGIApplication([
    webapp2.Route('/', handler=MainPage, handler_method='get_main'),
    webapp2.Route('/course/<org>/<number>/<semester>', handler=MainPage, handler_method='get_course'),
    webapp2.Route('/chapter/<org>/<number>/<semester>/<url_name>', handler=MainPage, handler_method='get_chapter'),
    webapp2.Route('/problem/<org>/<number>/<semester>/<url_name>', handler=MainPage, handler_method='get_problem'),
    webapp2.Route('/video/<org>/<number>/<semester>/<url_name>', handler=MainPage, handler_method='get_video'),
    webapp2.Route('/html/<org>/<number>/<semester>/<url_name>', handler=MainPage, handler_method='get_html'),
    webapp2.Route('/axis/<org>/<number>/<semester>', handler=MainPage, handler_method='get_axis'),
    webapp2.Route('/table/<org>/<number>/<semester>/<table>', handler=MainPage, handler_method='get_table'),
    webapp2.Route('/table/<database>/<table>', handler=MainPage, handler_method='get_table'),
    webapp2.Route('/get/<org>/<number>/<semester>/usage_stats', handler=MainPage, handler_method='ajax_get_usage_stats'),
    webapp2.Route('/get/<org>/<number>/<semester>/<problem_url_name>/problem_stats', handler=MainPage, handler_method='ajax_get_problem_stats'),
], debug=True, config=config)
