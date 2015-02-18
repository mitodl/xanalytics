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
from custom_reports import CustomReportRoutes
from reports import Reports
from collections import defaultdict, OrderedDict
from templates import JINJA_ENVIRONMENT

# from gviz_data_table import encode
# from gviz_data_table import Table

from google.appengine.api import memcache

mem = memcache.Client()

#-----------------------------------------------------------------------------

class MainPage(auth.AuthenticatedHandler, DataStats, DataSource, Reports):
    '''
    Main python class which displays views.
    '''

    @auth_required
    def get_main(self):
        '''
        Main page: show list of all courses
        '''
        courses = self.get_course_listings()

        # logging.info('course listings: %s' % courses['data'])

        def add_link(xstr, row=None):
            '''add link to course page to table element'''
            cid =  row.get('course_id', None)
            if cid:
                return "<a href=/course/%s>%s</a>" % (cid, xstr)
            else:
                return xstr
                
        html = self.list2table(map(DataTableField, 
                                   [{'field': 'launch', 'title':'Course launch', 'width': '12%'},
                                    {'field': 'course_number', 'title': 'Course #', 'width': '5%'}, 
                                    {'field': 'course_image', 'title': 'Course image'}, 
                                    {'field': 'title', 'title': 'Course Title', 'width': '40%'},
                                    {'field': 'course_id', 'title': 'course ID', 'width': '12%'},
                                   ]), 
                               courses['data'],
                               eformat={'course_number': add_link, 'title': add_link},
                           )

        data = self.common_data
        data.update({'data': {},
                     'is_staff': self.is_superuser(),
                     'is_pm': self.is_pm(),
                     'table': html,
                 })
        template = JINJA_ENVIRONMENT.get_template('courses.html')
        self.response.out.write(template.render(data))


    @auth_required
    def ajax_switch_collection(self):
        '''
        Switch collection to that specified.
        '''
        if not self.user in self.AUTHORIZED_USERS:	# require superuser
            return self.no_auth_sorry()

        selection = self.request.GET.get('selection', None)
        if selection is None:
            selection = self.request.POST.get('selection', None)

        if selection is None:
            logging.error("[ajax_switch_selection] Error! selection=%s" % selection)

        collection = selection.split('Option:', 1)[-1]
        logging.info("="*50 + " collection=%s, selection=%s" % (collection, selection))
        self.set_current_collection(collection)

        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps({'ok': True, 
                                            'dataset_latest': self.use_dataset_latest(),
                                            'collection_name': self.current_collection(),
                                            'collections_available': self.collections_available(),
                                            }))
        # self.session_store.save_sessions(self.response)

    @auth_required
    def ajax_get_usage_stats(self, org=None, number=None, semester=None):

        course_id = '/'.join([org, number, semester])
        usdat = self.compute_usage_stats(course_id)['data'][0]
        # categories = ['registered', 'viewed', 'explored']
        data = {'data': [usdat] }

        # logging.info('ajax_get_usage_stats data=%s' % data)

        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))
        
    @auth_required
    def ajax_get_enrollment_stats(self, org=None, number=None, semester=None):
        '''
        Return enrollment stats in "series" format for HighCharts.
        Use course listings to determine start date
        '''
        course_id = '/'.join([org, number, semester])
        courses = self.get_course_listings()
        start = courses['data_by_key'][course_id]['launch']

        (y,m,d) = map(int, start.split('-'))
        start_dt = datetime.datetime(y, m, d)
        start_dt = start_dt - datetime.timedelta(days=32*9)	# start plot 9 months before launch
        start_str = start_dt.strftime('%Y-%m-%d')

        end_dt = start_dt + datetime.timedelta(days=32*1)	# default position for end selector
        end_str = end_dt.strftime('%Y-%m-%d')
        logging.info('initial start_dt=%s, end_dt=%s' % (start_dt, end_dt))

        bqdat = self.compute_enrollment_by_day(course_id, start=start_str)
        dtrange = ['2199-12-31', '1900-01-01']

        def getrow(x, field, scale):
            dtstr = x['date']
            if dtstr < dtrange[0]:	# min max dates from actual data
                dtrange[0] = dtstr
            if dtstr > dtrange[1]:
                dtrange[1] = dtstr
            ts = self.datetime2milliseconds(dtstr=dtstr)  # (dt - datetime.datetime(1970, 1, 1)).total_seconds() * 1000
            cnt = int(x[field])
            return [ts, cnt]

        def getseries(field):
            return {'name': field['name'], 'data': [ getrow(x, field['field'], field['scale']) for x in bqdat['data'] ]}

        def mkf(field, name, scale=1):
            return {'field': field, 'name': name, 'scale': scale}

        fields = [mkf('nenroll_cum', 'cumulative enrollment')]
        stats = [ getseries(sname) for sname in fields ]

        dtrange = [ datetime.datetime(*map(int, x.split('-'))) for x in dtrange ]
        start_dt = max(dtrange[0], start_dt)
        end_dt =  max(dtrange[0], end_dt)
        if end_dt == start_dt:
            end_dt = end_dt + datetime.timedelta(days=32*2)
        end_dt =  min(dtrange[1], end_dt)
        logging.info('dtrange=%s, actual start_dt=%s, end_dt=%s' % (dtrange, start_dt, end_dt))

        data = {'series': stats,
                'start_dt': self.datetime2milliseconds(start_dt),
                'end_dt': self.datetime2milliseconds(end_dt),
        }

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
        pstats = ps['data_by_key'].get(problem_url_name, [])
        # logging.info('pstats = %s' % pstats)

        data = {'data': [ pstats ] }

        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))

    @auth_required
    def ajax_get_problem_answer_histories(self, org=None, number=None, semester=None, problem_url_name=None):

        course_id = '/'.join([org, number, semester])

        pah = self.select_problem_answer_histories(course_id, problem_url_name)

        # reformat student answers to be readable
        # also compute histogram
        histograms = defaultdict(lambda: defaultdict(int))

        latest_date = "0"

        for entry in pah['data']:
            entry['time'] = self.fix_date(entry['time'])
            if entry['time'] > latest_date:
                latest_date = entry['time']
            sa = entry['student_answers']
            sadat = json.loads(sa)
            sastr = "<table>"
            keys = sadat.keys()
            keys.sort()
            for k  in keys:	# merge dynamath with actual entry
                if k.endswith('_dynamath'):
                    aid = k.rsplit('_',1)[0]
                    if sadat[aid].strip():
                        sadat[aid] += u' \u21d2 ' + sadat[k]

            def fix_choice(citem):
                def choice2letter(m):
                    return chr(ord('A')+int(m.group(1)))
                return re.sub('choice_(\d+)', choice2letter, citem)

            for k  in keys:
                if k.endswith('_dynamath'):
                    continue
                answer_id = '_'.join(k.rsplit('_',2)[1:])  # see edx_platform/common/lib/capa/capa/capa_problem.py
                answer = sadat[k]
                hist_done = False
                if type(answer)==str and answer.startswith("[u'choce_") and answer.strip():
                    answer = answer.replace("u'","")
                elif type(answer)==list:		# for lists, make histogram of each item separately
                    answer = map(fix_choice, answer)
                    for answer_item in answer:
                        histograms[answer_id][answer_item] += 1
                        hist_done = True
                    # answer = str([str(x) for x in answer])
                    answer = ', '.join(answer)
                elif type(answer) in [str, unicode] and ('%20' in answer) and answer.strip():
                    answer = urllib.unquote(answer).strip()

                if type(answer) in [str, unicode] and answer.startswith('choice_'):
                    answer = fix_choice(answer)

                if not hist_done and answer.strip():
                    histograms[answer_id][answer] += 1
                sastr += "<tr><td>%s:</td><td>%s</td></tr>" % (answer_id, answer)
            sastr += "</table>"
            entry['answer'] = sastr

        # chop histogram tables into just top 20
        for aid, hdat in histograms.items():
            topitems = hdat.items()
            topitems.sort(key=lambda(x): x[1], reverse=True)
            topitems = topitems[:20]
            histograms[aid] = topitems

        # also order the histograms by aid
        histograms = OrderedDict(sorted(histograms.items()))

        # logging.info(json.dumps(histograms, indent=4))

        data = {'data': pah['data'],
                'items': histograms.keys(),
                'histograms': histograms,     # { k: v.items() for (k,v) in histograms.items()},
                'data_date': latest_date[:16],
        }

        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))

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

        if start_dt > datetime.datetime.now():
            start_dt = start_dt - datetime.timedelta(days=7*10)	# start plot 10 weeks before launch
        else:
            start_dt = start_dt - datetime.timedelta(days=14)	# start plot 2 weeks before launch

        # logging.info("start_str = %s" % start_str)
        end_dt = start_dt + datetime.timedelta(days=32*4)	# default position for end selector
        end_str = end_dt.strftime('%Y-%m-%d')

        if start_dt >= end_dt:
            start_dt = datetime.datetime(2014, 9, 1)
        start_str = start_dt.strftime('%Y-%m-%d')
        the_end = self.get_collection_metadata('END_DATE', '2015-01-01')
        if end_str > '2015-01-01':
            the_end = end_str

        try:
            bqdat = self.compute_activity_by_day(course_id, start=start_str, end=the_end)
        except Exception as err:
            logging.error("failed in calling compute_activity_by_day, err=%s" % str(err))
            data = {'series': [], 
                    'start_dt': self.datetime2milliseconds(start_dt),
                    'end_dt': self.datetime2milliseconds(end_dt),
                    'data_date': '',
            }

            self.response.headers['Content-Type'] = 'application/json'   
            self.response.out.write(json.dumps(data))
            return


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
                # 'data_date': bqdat.get('depends_on', ['.'])[0].split('.',1)[1],
                'data_date': (bqdat['data'] or [{'date': None}])[-1]['date'],
                'launch': start,
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
                link = "<a href='/{category}/{course_id}/{url_name}'>{txt}</a>".format(txt=(txt.encode('utf8') or "none"),
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
            txt = txt.encode('utf8')
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
                'stats_table': stats_table,
                'data_date': str(self.course_axis['lastModifiedTime'])[:16],
        }
        tabledata = json.dumps(data)
        self.response.out.write(tabledata)


    @auth_required
    def ajax_get_geo_stats(self, org=None, number=None, semester=None):
        '''
        geographic stats for a course
        '''
        course_id = '/'.join([org, number, semester])
        bqdat = self.compute_geo_stats(course_id)

        def mkpct(a,b):
            if not b:
                return ""
            if int(b)==0:
                return ""
            return "%6.1f" % (int(a) / float(b) * 100)

        def getrow(x):
            if not x['countryLabel']:
                x['countryLabel'] = 'Unknown'
            x['cert_pct'] = mkpct(x['ncertified'], x['nregistered'])
            x['cert_pct_of_viewed'] = mkpct(x['ncertified'], x['nviewed'])
            x['verified_cert_pct'] = mkpct(x['n_verified_certified'], x['n_verified_id'])
            x['avg_hours'] = "%8.1f" % (float(x['avg_of_sum_dt'] or 0)/60/60)	# hours
            x['avg_hours_certified'] = "%8.1f" % (float(x['certified_sum_dt'] or 0)/60/60)	# hours
            return { 'z': int(x['nregistered']),
                     'cc': x['cc'],
                     'name': x['countryLabel'],
                     'nverified': x['n_verified_id'],
                     'ncertified': x['ncertified'],
                     'cert_pct': x['cert_pct'],
                 }

        series = [ getrow(x) for x in bqdat['data'] ]

        #top_by_reg = sorted(bqdat['data'], key=lambda x: int(x['nregistered']), reverse=True)[:10]
        # logging.info("top_by_reg = %s" % json.dumps(top_by_reg, indent=4))

        data = {'series': series,
                'table': bqdat['data'],
                'data_date': str(bqdat['lastModifiedTime'])[:16],
        }

        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))

        
    @auth_required
    def get_course(self, org=None, number=None, semester=None):
        '''
        single course analytics view

        - overall statistics (number of components of various categories)
        - show table of chapters
        '''
        course_id = '/'.join([org, number, semester])

        # handle forced recomputation requests
        action = self.request.POST.get('action', None)
        logging.info('post keys = %s' % self.request.POST.keys())
        logging.info('post action = %s' % action)
        if action=='force recompute enrollment':
            self.reset_enrollment_by_day(course_id)

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

        data = self.common_data.copy()
        data.update({'course_id': course_id,
                     'fields': tablefields,
                     'table': tablehtml,
                     'is_staff': self.is_superuser(),
                     'is_pm': self.is_pm(),
                     'image': self.get_course_image(course_id),
                     'nav_is_active': self.nav_is_active('onecourse'),
                     'custom_report': self.custom_report_container(self.is_authorized_for_custom_report, 
                                                                   course_id=course_id),
                 })
        
        template = JINJA_ENVIRONMENT.get_template('one_course.html')
        self.response.out.write(template.render(data))
        
    @auth_required
    def get_axis(self, org=None, number=None, semester=None):
        '''
        show full course axis -- mainly for debugging
        '''
        course_id = '/'.join([org, number, semester])
        caxis = self.load_course_axis(course_id, dtype='data')

        # logging.info("caxis=%s" % json.dumps(caxis, indent=4))

        for cae in caxis:
            try:
                # caxis[row]['name'] = fix_bad_unicode(caxis[row]['name'])
                #caxis[row]['name'] = caxis[row]['name'].replace('\u2013','-')
                #caxis[row]['name'] = str(caxis[row]['name'])
                cae['name'] = unidecode(cae['name'])	# desparation: perhaps data wasn't encoded properly originally?
                if cae['gformat']:
                    cae['gformat'] = unidecode(cae['gformat'])	# desparation: perhaps data wasn't encoded properly originally?
                # cae['name'] = str(cae['name'])
            except Exception as err:
                print "unicode error for course axis row=%s, name=" % repr(cae), repr(cae['name'])
                print "type = ", type(cae['name'])
                raise

        if 1:
            fields = ['category', 'index', 'url_name', 'name', 'gformat', 'due', 'start', 
                      'module_id', 'path', 'data_ytid', 'data_weight', 'chapter_mid']
            #fields = ['category', 'index', 'name', 'due', 'start', 
            #          'module_id', 'path', 'data_ytid', 'data_weight', 'chapter_mid']
            tablehtml = self.list2table(fields,
                                        caxis,
                                        eformat={'due': self.fix_date, 'start': self.fix_date}, )

        data = self.common_data
        data.update({'course_id': course_id,
                     'table': tablehtml,
                 })
        
        template = JINJA_ENVIRONMENT.get_template('course_axis.html')
        self.response.headers['Content-Type'] = 'text/html; charset=utf-8'
        self.response.out.write(template.render(data))
        

    @auth_required
    def ajax_get_table_data(self, org=None, number=None, semester=None, table=None):
        '''
        show arbitrary table from bigquery -- mainly for debugging - ajax data 
        '''
        course_id = '/'.join([org, number, semester])
        dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.use_dataset_latest())

        if ('person' in table) or ('track' in table) or ('student' in table):
            if not self.does_user_have_role('instructor', course_id):
                return self.no_auth_sorry()

        # DataTables server-side processing: http://datatables.net/manual/server-side

        draw = int(self.request.POST['draw'])
        start = int(self.request.POST['start'])
        length = int(self.request.POST['length'])

        bqdata = self.cached_get_bq_table(dataset, table, startIndex=start, maxResults=length)
        self.fix_bq_dates(bqdata)
        
        logging.info('get draw=%s, start=%s, length=%s' % (draw, start, length))

        if 0:
            for row in bqdata['data']:
                for key in row:
                    row[key] = row[key].encode('utf-8')

        data = self.common_data
        data.update({'data': bqdata['data'],
                     'draw': draw,
                     'recordsTotal': bqdata['numRows'],
                     'recordsFiltered': bqdata['numRows'],
                 })
        
        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))

    @auth_required
    def get_table(self, dataset=None, table=None, org=None, number=None,semester=None):
        '''
        show arbitrary table from bigquery -- mainly for debugging
        '''
        if dataset is None:
            course_id = '/'.join([org, number, semester])
            dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.use_dataset_latest())
            if not self.is_user_authorized_for_course(course_id):
                return self.no_auth_sorry()
            if ('person' in table) or ('track' in table) or ('student' in table):
                if not self.does_user_have_role('instructor', course_id):
                    return self.no_auth_sorry()
                    
        else:
            course_id = None
            if not self.user in self.AUTHORIZED_USERS:
                return self.no_auth_sorry()

        tableinfo = bqutil.get_bq_table_info(dataset, table)

        fields = tableinfo['schema']['fields']
        field_names = [x['name'] for x in fields]

        tablecolumns = json.dumps([ { 'data': x, 'title': x, 'class': 'dt-center' } for x in field_names ])
        logging.info(tablecolumns)

        data = self.common_data
        data.update({'dataset': dataset,
                     'table': table,
                     'course_id': course_id,
                     'tablecolumns': tablecolumns,
                 })
        
        template = JINJA_ENVIRONMENT.get_template('show_table.html')
        self.response.out.write(template.render(data))

config = {}
config['webapp2_extras.sessions'] = {
    'secret_key': local_config.SESSION_SECRET_KEY,
}

ROUTES = [

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
    webapp2.Route('/get/<org>/<number>/<semester>/enrollment_stats', handler=MainPage, handler_method='ajax_get_enrollment_stats'),
    webapp2.Route('/get/<org>/<number>/<semester>/usage_stats', handler=MainPage, handler_method='ajax_get_usage_stats'),
    webapp2.Route('/get/<org>/<number>/<semester>/course_stats', handler=MainPage, handler_method='ajax_get_course_stats'),
    webapp2.Route('/get/<org>/<number>/<semester>/geo_stats', handler=MainPage, handler_method='ajax_get_geo_stats'),
    webapp2.Route('/get/<org>/<number>/<semester>/<url_name>/chapter_stats', handler=MainPage, handler_method='ajax_get_chapter_stats'),
    webapp2.Route('/get/<org>/<number>/<semester>/<problem_url_name>/problem_stats', handler=MainPage, handler_method='ajax_get_problem_stats'),
    webapp2.Route('/get/<org>/<number>/<semester>/<table>/table_data', handler=MainPage, handler_method='ajax_get_table_data'),
    webapp2.Route('/get/<org>/<number>/<semester>/<problem_url_name>/problem_histories', handler=MainPage, handler_method='ajax_get_problem_answer_histories'),
    webapp2.Route('/get/dashboard/geo_stats', handler=MainPage, handler_method='ajax_dashboard_get_geo_stats'),

    webapp2.Route('/get/switch_collection', handler=MainPage, handler_method='ajax_switch_collection'),
]

ROUTES += DashboardRoutes
ROUTES += AdminRoutes
ROUTES += DeveloperRoutes
ROUTES += CustomReportRoutes

application = webapp2.WSGIApplication(ROUTES, debug=True, config=config)
