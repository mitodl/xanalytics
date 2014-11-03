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

from auth import auth_required
from stats import DataStats
from datatable import DataTableField
from collections import defaultdict, OrderedDict

import jinja2

# from gviz_data_table import encode
# from gviz_data_table import Table

from google.appengine.api import memcache

mem = memcache.Client()

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

#-----------------------------------------------------------------------------

class MainPage(auth.AuthenticatedHandler, DataStats):
    '''
    Main python class which displays views.
    '''

    GSROOT = local_config.GOOGLE_STORAGE_ROOT
    ORGNAME = local_config.ORGANIZATION_NAME
    MODE = local_config.MODE
    USE_LATEST = local_config.DATA_DATE=='latest'	# later: generalize to dataset for specific date

    IM_WIDTH = 374/2
    IM_HEIGHT = 200/2
    bqdata = {}

    common_data = {'orgname': ORGNAME,
                   'mode': MODE,
    }

    #-----------------------------------------------------------------------------

    def get_course_listings(self):
        dataset = 'courses'
        table = 'listings'
        courses = self.cached_get_bq_table(dataset, table, key={'name': 'course_id'})

        for k in courses['data']:
            cid = k['course_id']
            if not cid:
                logging.info('oops, bad course_id! line=%s' % k)
                continue
            k['course_image'] = self.get_course_image(cid)
            k['title'] = k['title'].encode('utf8')
            (m,d,y) = map(int, k['courses_launch'].split('/'))
            ldate = "%04d-%02d-%02d" % (y,m,d)
            k['launch'] = ldate
            courses['data_by_key'][cid]['launch'] = ldate
        return courses

    @auth_required
    def get_main(self):
        '''
        Main page: show list of all courses
        '''
        courses = self.get_course_listings()

        # logging.info('course listings: %s' % courses['data'])

        html = self.list2table(map(DataTableField, 
                                   [{'field': 'launch', 'title':'Course launch'},
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
        if self.USE_LATEST:
            cdir = cdir + "/latest"
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
        dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.USE_LATEST)
        table = "course_axis"
        key={'name': 'url_name'}
        return self.cached_get_bq_table(dataset, table, key=key, drop=['data'])['data_by_key']


    def load_person_course(self, course_id):
        '''
        Get person_course table from BQ.  Use memcache.

        The person_course table has these relevant fields (among many):

        username, viewed, explored, ip
        '''
        dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.USE_LATEST)
        table = "person_course"
        key = None
        return self.cached_get_bq_table(dataset, table)

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

        # logging.info('ajax_get_usage_stats data=%s' % data)

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

    @staticmethod
    def datetime2milliseconds(dt):
        return (dt - datetime.datetime(1970, 1, 1)).total_seconds() * 1000

    @auth_required
    def ajax_get_activity_stats(self, org=None, number=None, semester=None):
        '''
        Return activity stats in "series" format for HighCharts
        See http://www.highcharts.com/docs/chart-concepts/series

        Use course listings to determine start date
        '''
        course_id = '/'.join([org, number, semester])
        courses = self.get_course_listings()
        start = courses['data_by_key'][course_id]['launch']
        (y,m,d) = map(int, start.split('-'))
        start_dt = datetime.datetime(y, m, d)
        start_dt = start_dt - datetime.timedelta(days=14)	# start plot 2 weeks before launch
        start_str = start_dt.strftime('%Y-%m-%d')
        logging.info("start_str = %s" % start_str)
        end_dt = start_dt + datetime.timedelta(days=32*4)	# default position for end selector
        end_str = end_dt.strftime('%Y-%m-%d')

        bqdat = self.compute_activity_by_day(course_id, start=start_str)
        def getrow(x, field, scale):
            #return [x[k] for k in ['date', 'nevents', 'nforum']]
            (y,m,d) = map(int, x['date'].split('-'))
            dt = datetime.datetime(y,m,d)
            ts = self.datetime2milliseconds(dt)  # (dt - datetime.datetime(1970, 1, 1)).total_seconds() * 1000
            cnt = int(x[field]) / scale
            return [ts, cnt]

        def getseries(field):
            return {'name': field['name'], 'data': [ getrow(x, field['field'], field['scale']) for x in bqdat['data'] ]}

        def mkf(field, name, scale):
            return {'field': field, 'name': name, 'scale': scale}

        fields = [mkf('nevents', '# events / 10', 10), 
                  mkf('nforum', '# forum events', 1),
                  mkf('nvideo', '# video events', 1),
                  mkf('nproblem_check', '# problem check events', 1),
                  mkf('nshow_answer', '# show answer events', 1)]
        stats = [ getseries(sname) for sname in fields ]
        #stats = [ getseries(sname) for sname in ['nevents'] ]

        data = {'series': stats,
                'start_dt': self.datetime2milliseconds(start_dt),
                'end_dt': self.datetime2milliseconds(end_dt),
        }

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
    def ajax_get_chapter_stats(self, org=None, number=None, semester=None, url_name=None):
        '''
        single chapter analytics view - actual data
        '''
        
        course_id = '/'.join([org, number, semester])
        caxis = self.load_course_axis(course_id)
        the_chapter = caxis[url_name]
        chapter_mid = the_chapter['module_id']

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

        tabledata = json.dumps({'data': [ makerow(x) for x in ccontents ]})
        self.response.out.write(tabledata)

    @auth_required
    def get_chapter(self, org=None, number=None, semester=None, url_name=None):
        '''
        single chapter analytics view: container for table data

        - sequentials and problems
        '''
        course_id = '/'.join([org, number, semester])
        caxis = self.load_course_axis(course_id)

        # get chapter info
        the_chapter = caxis[url_name]
        chapter_mid = the_chapter['module_id']
        chapter_name = the_chapter['name']

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


        tablehtml = self.list2table(fields, [])
        tablefields = json.dumps([x.colinfo() for x in fields])

        data = self.common_data
        data.update({'fields': tablefields,
                     'table': tablehtml,
                     'course_id': course_id,
                     'chapter_name': chapter_name,
                     'url_name': url_name,
                 })

        template = JINJA_ENVIRONMENT.get_template('chapter.html')
        self.response.out.write(template.render(data))
        

    @staticmethod
    def fix_date(x):
        if x:
            return str(datetime.datetime.utcfromtimestamp(float(x)))
        return ''

    @auth_required
    def ajax_get_course_stats(self, org=None, number=None, semester=None):
        '''
        single course analytics view - data only
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
            txt = txt.encode('utf-8')
            return "<a href='/chapter/{course_id}/{url_name}'>{txt}</a>".format(txt=txt,
                                                                                course_id=course_id,
                                                                                url_name=rdat['url_name'])
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

        data = {'data': [ makerow(x) for x in caxis.values() if x['category']=='chapter'],
                'stats_columns': [ {'className': 'dt-center'}] *len(stats_fields),
                'stats_table': stats_table
        }
        tabledata = json.dumps(data)
        self.response.out.write(tabledata)

        
    @auth_required
    def get_course(self, org=None, number=None, semester=None):
        '''
        single course analytics view

        - overall statistics (number of components of various categories)
        - show table of chapters
        '''
        course_id = '/'.join([org, number, semester])

        # show table with just chapters, and present sequentials as extra information when clicked
        fields = [ DataTableField(x) for x  in [{'field': 'index', 'title': 'Time index', 'width': '8%', 'class': 'dt-center'}, 
                                                {'field': 'name', 'title': "Chapter name"},
                                                {'field': 'start', 'title': "Start date", 'width': '18%'},
                                                {'field': 'nuser_views', 'title': '# user-views', 'width': '10%', 'class': 'dt-center'},
                                               ] ]

        # logging.info('sm_usage:')
        # logging.info(self.bqdata['stats_module_usage']['data_by_key'])

        tablehtml = self.list2table([' '] + fields, [])
        tablefields = json.dumps([
            {
                "class":          'details-control',
                "orderable":      False,
                "data":           None,
                'width': '5%',
                "defaultContent": ''
            },] +  [x.colinfo() for x in fields])

        data = self.common_data
        data.update({'course_id': course_id,
                     'fields': tablefields,
                     'table': tablehtml,
                     # 'stats_table': stats_table,
                     # 'stats_columns': json.dumps([ {'className': 'dt-center'}] *len(stats_fields)),
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
        

    @auth_required
    def get_table(self, dataset=None, table=None, org=None, number=None,semester=None):
        '''
        show arbitrary table from bigquery -- mainly for debugging
        '''
        if dataset is None:
            course_id = '/'.join([org, number, semester])
            dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.USE_LATEST)
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

    # html pages

    webapp2.Route('/', handler=MainPage, handler_method='get_main'),
    webapp2.Route('/course/<org>/<number>/<semester>', handler=MainPage, handler_method='get_course'),
    webapp2.Route('/chapter/<org>/<number>/<semester>/<url_name>', handler=MainPage, handler_method='get_chapter'),
    webapp2.Route('/problem/<org>/<number>/<semester>/<url_name>', handler=MainPage, handler_method='get_problem'),
    webapp2.Route('/video/<org>/<number>/<semester>/<url_name>', handler=MainPage, handler_method='get_video'),
    webapp2.Route('/html/<org>/<number>/<semester>/<url_name>', handler=MainPage, handler_method='get_html'),
    webapp2.Route('/axis/<org>/<number>/<semester>', handler=MainPage, handler_method='get_axis'),
    webapp2.Route('/table/<org>/<number>/<semester>/<table>', handler=MainPage, handler_method='get_table'),
    webapp2.Route('/table/<database>/<table>', handler=MainPage, handler_method='get_table'),

    # ajax calls

    webapp2.Route('/get/<org>/<number>/<semester>/activity_stats', handler=MainPage, handler_method='ajax_get_activity_stats'),
    webapp2.Route('/get/<org>/<number>/<semester>/usage_stats', handler=MainPage, handler_method='ajax_get_usage_stats'),
    webapp2.Route('/get/<org>/<number>/<semester>/course_stats', handler=MainPage, handler_method='ajax_get_course_stats'),
    webapp2.Route('/get/<org>/<number>/<semester>/<url_name>/chapter_stats', handler=MainPage, handler_method='ajax_get_chapter_stats'),
    webapp2.Route('/get/<org>/<number>/<semester>/<problem_url_name>/problem_stats', handler=MainPage, handler_method='ajax_get_problem_stats'),
], debug=True, config=config)
