#
# dashboard methods
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

from collections import defaultdict, OrderedDict
from stats import DataStats
from datatable import DataTableField
from datasource import DataSource

from auth import auth_required, auth_and_role_required

# from google.appengine.api import memcache
# mem = memcache.Client()

JINJA_ENVIRONMENT = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__)),
    extensions=['jinja2.ext.autoescape'],
    autoescape=True)

class Dashboard(auth.AuthenticatedHandler, DataStats, DataSource):
    '''
    Methods for cross-course summary dashboard
    '''

    @auth_and_role_required(role='pm')
    @auth_required
    def get_dashboard(self):
        '''
        Dashboard page: show cross-course comparisons
        '''
        courses = self.get_course_listings()
        data = self.common_data
        html = self.list2table(['Registration Open', 'course_id', 'title', 'Course Launch', 'Course Wrap', 'New or Rerun', 'Instructors'],
                               courses['data'])
        data.update({'is_staff': self.is_superuser(),
                     'courses': courses,
                     'table': html,
                     'ncourses': len(courses['data']),
                 })
        template = JINJA_ENVIRONMENT.get_template('dashboard.html')
        self.response.out.write(template.render(data))

    @auth_required
    def ajax_dashboard_get_geo_stats(self):
        '''
        geographic stats across courses, with fields:

        cc
        countryLabel
        ncertified
        nregistered
        nviewed
        nexplored
        nverified
        ncert_verified
        avg_certified_dt

        '''
        bqdat = self.get_report_geo_stats()

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
            x['verified_cert_pct'] = mkpct(x['ncert_verified'], x['nverified'])
            x['avg_hours_certified'] = "%8.1f" % (float(x['avg_certified_dt'] or 0)/60.0/60)	# hours
            x['nregistered'] = int(x['nregistered'])
            return { 'z': int(x['nregistered']),
                     'cc': x['cc'],
                     'name': x['countryLabel'],
                     'nverified': x['nverified'],
                     'ncertified': x['ncertified'],
                     'cert_pct': x['cert_pct'],
                     
                 }

        series = [ getrow(x) for x in bqdat['data'] ]
        # logging.info('series=%s' % json.dumps(series[:10], indent=4))
        tfields = ['nregistered', 'ncertified', 'nverified', 'nviewed', 'nexplored'] 
        totals = { field: sum([ int(x[field]) for x in bqdat['data']]) for field in tfields}

        #top_by_reg = sorted(bqdat['data'], key=lambda x: int(x['nregistered']), reverse=True)[:10]
        # logging.info("top_by_reg = %s" % json.dumps(top_by_reg, indent=4))

        data = {'series': series,
                'table': bqdat['data'],
                'totals': totals,
                'last_updated': str(bqdat['lastModifiedTime']).rsplit(':',1)[0],
        }

        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))

    @auth_required
    def ajax_dashboard_get_courses_by_time(self):
        '''
        Return data for number of courses by time, showing
        when courses open for registration, when they start,
        and when they end.
        '''
        courses = self.get_course_listings()

        def mkcum(field):
            cnt = 0
            dates = [{'date': x[field], 'num': x['Course Number'], 
                      'title': x['Title'],
                      'course_id': x['course_id'],
                      'ms': self.datetime2milliseconds(dtstr=x[field])} for x in courses['data']]
            #logging.info(dates)
            dates.sort(key=lambda x: x['ms'])
            data = []
            flags = []
            for x in dates:
                xms = x['ms']
                if xms is None:
                    continue
                data.append([ xms, cnt ])	# step function at this date
                cnt += 1
                data.append([ xms, cnt ])
                flags.append({'x': xms, 'title': x['num'], 'text': '%s: %s' % (x['course_id'], x['title'])})
            return data, flags

        # registration opening
        rodat, roflags = mkcum('Registration Open')

        data = {'series': [ {'name': 'Registration Open', 'id': 'reg_open', 'data': rodat},
                            {'type': 'flags', 'data': roflags, 'onSeries': 'reg_open'},
                        ],
        }
        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))


    @auth_required
    def ajax_dashboard_get_enrollment_by_time(self):
        '''
        Return data for enrollment by time.
        '''
        ebyday = self.compute_overall_enrollment_by_day()

        cum_reg = []
        net_reg = []

        for row in ebyday['data']:
            dtms = self.datetime2milliseconds(dtstr=row['date'])
            nec = int(row['nregistered_ever_cum'])
            if nec > 0:
                cum_reg.append( [ dtms, nec ])
            nnc = int(row['nregistered_net_cum'])
            if nnc > 0:
                net_reg.append( [ dtms, nnc ])

        # average new enrollment per day
        enroll_rate_avg = (cum_reg[-1][1] - cum_reg[0][1]) * 1.0 / ((cum_reg[-1][0] - cum_reg[0][0])/1000.0/60/60/24)

        logging.info("enroll_rate_avg = %s" % enroll_rate_avg)

        data = {'series': [ {'name': 'Cumulative Registration', 'id': 'cum_reg', 'data': cum_reg},
                            {'name': 'Net Registration (includes un-registration)', 'id': 'net_reg', 'data': net_reg},
                            # {'type': 'flags', 'data': roflags, 'onSeries': 'reg_open'},
                        ],
                'enroll_rate_avg': "%9.1f" % enroll_rate_avg,
        }
        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(data))

        

DashboardRoutes = [
# displayed page routes
    webapp2.Route('/dashboard', handler=Dashboard, handler_method='get_dashboard'),

# ajax routes
    webapp2.Route('/dashboard/get/geo_stats', handler=Dashboard, handler_method='ajax_dashboard_get_geo_stats'),
    webapp2.Route('/dashboard/get/courses_by_time', handler=Dashboard, handler_method='ajax_dashboard_get_courses_by_time'),
    webapp2.Route('/dashboard/get/enrollment_by_time', handler=Dashboard, handler_method='ajax_dashboard_get_enrollment_by_time'),
]
