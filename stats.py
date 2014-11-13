#
# python functions which compute statistics tables (no views)
#
# This produces much of the data to be obtained via AJAX calls, but the
# AJAX calls themselves should go elsewhere.
#

import re
import datetime
import bqutil
import local_config
import logging
from collections import defaultdict, OrderedDict
from datatable import DataTableField
from unidecode import unidecode

from google.appengine.api import memcache

mem = memcache.Client()

class DataStats(object):

    GSROOT = local_config.GOOGLE_STORAGE_ROOT
    USE_LATEST = local_config.DATA_DATE=='latest'	# later: generalize to dataset for specific date
    IM_WIDTH = 374/2
    IM_HEIGHT = 200/2
    bqdata = {}

    ORGNAME = local_config.ORGANIZATION_NAME
    MODE = local_config.MODE

    common_data = {'orgname': ORGNAME,
                   'mode': MODE,
    }

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
            
        def map_format(name, row):
            dtf = DataTableField(name)
            field = dtf.field
            if dtf.icon == 'delete':
                return "<button type='submit' name='do-delete' value='%s'><img src='/images/Delete_Icon-small.png'/></button>" % row.get(field, '')
            estr = (row.get(field, '') or '')
            if eformat is None:
                return estr
            elif name in eformat:
                return eformat[field](estr)
            return estr

        for k in data:
            datatable += '<tr>'
            if type(k) in [dict, OrderedDict, defaultdict]:
                row = [map_format(name, k) for name in names]
            else:
                row = k
            for ent in row:
                if type(ent) in [str, unicode]:
                    try:
                        ent = ent.encode('utf8')
                    except:
                        try:
                            ent = unidecode(ent)
                        except Exception as err:
                            logging.error('[list2table] cannot encode unicode for entry %s' % repr(ent))
                            raise
                datatable += '<td {fmt}>{dat}</td>'.format(dat=ent, fmt=fmt)
                # datatable += '<td>%s</td>' % ent
            datatable += '</tr>\n'
        datatable += '''</tbody></table>\n'''
        return datatable
            
    #-----------------------------------------------------------------------------

    def compute_sm_usage(self, course_id):
        '''
        Compute usage stats from studentmodule table for course
        '''
        dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.USE_LATEST)
        sql = """
                SELECT 
                    module_type, module_id, count(*) as ncount 
                FROM [{dataset}.studentmodule] 
                group by module_id, module_type
                order by module_id
        """.format(dataset=dataset)

        table = 'stats_module_usage'
        key = {'name': 'module_id'}
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key,
                                        depends_on=['%s.studentmodule' % dataset, '%s.course_axis' % dataset ])

    def compute_problem_stats(self, course_id):
        '''
        Compute problem average grade, attempts
        '''
        dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.USE_LATEST)
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
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key,
                                        depends_on=['%s.problem_analysis' % dataset])


    def select_problem_answer_histories(self, course_id, url_name):
        '''
        Compute table of answers ever submitted for a given problem, as specified by a module_id.
        '''
        dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.USE_LATEST)
        org, num, semester = course_id.split('/')
        module_id = '%s/%s/problem/%s' % (org, num, url_name)
        sql = """
                SELECT '{course_id}' as course_id,
                    username,
                    time,
                    student_answers,
                    attempts,
                    success,
                    grade,
                FROM [{dataset}.problem_check]
                WHERE
                    module_id = "{module_id}"
                order by time
        """.format(dataset=dataset, course_id=course_id, module_id=module_id)

        table = 'problem_check_for_%s' % (url_name.replace(':','__').replace('-','_'))
        key = None
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key,
                                        depends_on=['%s.problem_check' % dataset])


    def compute_enrollment_by_day(self, course_id, start="2012-08-20", end="2115-01-01"):
        '''
        Compute enrollment by day, based on enrollday_* tables
        '''
        dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.USE_LATEST)	# where to store result
        input_dataset = bqutil.course_id2dataset(course_id, 'pcday')				# source data

        sql_enrollday = """
          SELECT 
              '{course_id}' as course_id,
              date,
              nenroll,
              sum(nenroll) over(order by date) as nenroll_cum,
          FROM (
                  SELECT 
                      date(time) as date,
                      sum(diff_enrollment) as nenroll,
                  FROM (
                   # TABLE_DATE_RANGE([{dataset}.enrollday_],
                   #                       TIMESTAMP('{start}'),
                   #                       TIMESTAMP('{end}'))) 
                   TABLE_QUERY({dataset}, 
                       "integer(regexp_extract(table_id, r'enrollday_([0-9]+)')) BETWEEN {start} and {end}"
                     )
                  )
                  group by date
                  order by date
        )
        group by date, nenroll
        order by date
        """.format(dataset=input_dataset, course_id=course_id, 
                   start=start.replace('-',''), 
                   end=end.replace('-',''))

        sql_enrollday2 = """
          SELECT 
              '{course_id}' as course_id,
              date,
              nenroll,
              sum(nenroll) over(order by date) as nenroll_cum,
          FROM (
                  SELECT 
                      date(time) as date,
                      sum(diff_enrollment_honor) as nenroll_honor,
                      sum(diff_enrollment_audit) as nenroll_audit,
                      sum(diff_enrollment_verified) as nenroll_verified,
        	      # and, for backwards compatibility with old enrollday_* :
                      sum(diff_enrollment_honor) + sum(diff_enrollment_audit) + sum(diff_enrollment_verified) as nenroll,
                  FROM (
                   # TABLE_DATE_RANGE([{dataset}.enrollday2_],
                   #                       TIMESTAMP('{start}'),
                   #                       TIMESTAMP('{end}'))) 
                   TABLE_QUERY({dataset}, 
                       "integer(regexp_extract(table_id, r'enrollday2_([0-9]+)')) BETWEEN {start} and {end}"
                     )
                  )
                  group by date
                  order by date
        )
        group by date, nenroll
        order by date
        """.format(dataset=input_dataset, course_id=course_id, 
                   start=start.replace('-',''), 
                   end=end.replace('-',''))

        sql_enrollday_all = """
          SELECT 
              '{course_id}' as course_id,
              date,
              nenroll,
              sum(nenroll) over(order by date) as nenroll_cum,
          FROM (
                  SELECT 
                      date(time) as date,
                      sum(diff_enrollment_honor) as nenroll_honor,
                      sum(diff_enrollment_audit) as nenroll_audit,
                      sum(diff_enrollment_verified) as nenroll_verified,
                      sum(diff_enrollment_honor) + sum(diff_enrollment_audit) + sum(diff_enrollment_verified) as nenroll,
                  FROM {dataset}.enrollday_all
                  group by date
                  order by date
        )
        group by date, nenroll
        order by date
        """.format(dataset=dataset, course_id=course_id)

        # special handling: use new enrollday_all tables if available, instead of enrollday* in *_pcday dataset
        tables = bqutil.get_list_of_table_ids(dataset)
        if 'enrollday_all' in tables:
            sql = sql_enrollday_all
            logging.info('[compute_enrollment_by_day] using enrollday_all for %s' % course_id)
            depends_on = [ "%s.enrollday_all" % dataset ]
        else:
            # old special handling: use new enrollday2_* tables if available, instead of enrollday_* 
            tables = bqutil.get_list_of_table_ids(input_dataset)
            prefixes = [x.split('_')[0] for x in tables]
            if 'enrollday2' in prefixes:
                sql = sql_enrollday2
                logging.info('[compute_enrollment_by_day] using enrollday2 for %s' % course_id)
                tpre = 'enrollday2'
            else:
                sql = sql_enrollday
                tpre = 'enrollday'
    
            latest_table = None
            for k in tables:
                if k.startswith('%s_' % tpre):
                    if latest_table is None or k > latest_table:
                        latest_table = k
            depends_on = ['%s.%s' % (input_dataset, latest_table)]

        logging.info('enrollment_day depends_on=%s' % depends_on)
        table = 'stats_enrollment_by_day'
        key = None
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key,
                                        depends_on=depends_on,
                                        logger=logging.error, ignore_cache=False)

    def reset_enrollment_by_day(self, course_id):
        dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.USE_LATEST)	# where to store result
        table = 'stats_enrollment_by_day'
        logging.info('[reset enrollment by day] removing table %s.%s...' % (dataset, table))
        memset = '%s.%s' % (dataset,table)
        mem.delete(memset)
        try:
            bqutil.delete_bq_table(dataset, table)
        except Exception as err:
            logging.error(err)

    def compute_activity_by_day(self, course_id, start="2012-08-20", end="2015-01-01"):
        '''
        Compute course activity by day, based on person_course_day tables
        '''
        dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.USE_LATEST)
        input_dataset = bqutil.course_id2dataset(course_id, 'pcday')
        sql = """
          SELECT 
              date(last_event) as date,
              sum(nevents) as nevents,
              sum(nvideo) as nvideo,
              sum(nshow_answer) as nshow_answer,
              sum(nproblem_check) as nproblem_check,
              sum(nforum) as nforum,
              sum(ntranscript) as ntranscript,
              sum(nseq_goto) as nseq_goto,
              sum(nseek_video) as nseek_video,
              sum(nprogcheck) as nprogcheck,
              sum(npause_video) as npause_video,
              sum(sum_dt) as sum_dt,
              avg(avg_dt) as avg_dt,
              sum(n_dt) as n_dt,
          FROM (TABLE_DATE_RANGE([{dataset}.pcday_],
                                  TIMESTAMP('{start}'),
                                  TIMESTAMP('{end}'))) 
          group by date
          order by date
        """.format(dataset=input_dataset, course_id=course_id, start=start, end=end)

        pcday_tables = bqutil.get_list_of_table_ids(input_dataset)
        last_pcday = None
        for k in pcday_tables:
            if k.startswith('pcday_'):
                if last_pcday is None or k > last_pcday:
                    last_pcday = k

        table = 'stats_activity_by_day'
        key = None
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key,
                                        depends_on=['%s.%s' % (input_dataset, last_pcday)],
                                        logger=logging.error)


    def compute_usage_stats(self, course_id):
        '''
        Compute usage stats, i.e. # registered, viewed, explored, based on person-course
        '''
        dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.USE_LATEST)
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
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key,
                                        depends_on=['%s.person_course' % dataset])


    def compute_geo_stats(self, course_id):
        '''
        Compute geographic distributions
        '''
        dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.USE_LATEST)
        sql = """
           SELECT '{course_id}' as course_id,
                   cc_by_ip as cc,
                   countryLabel as countryLabel,
                   count(*) as nregistered,
                   sum(case when viewed then 1 else 0 end) as nviewed,
                   sum(case when explored then 1 else 0 end) as nexplored,
                   sum(case when certified then 1 else 0 end) as ncertified,
    
                   sum(case when gender='m' then 1 else 0 end) as n_male,
                   sum(case when gender='f' then 1 else 0 end) as n_female,
    
                   sum(case when mode="verified" then 1 else 0 end) as n_verified_id,
                   sum(case when (certified and mode="verified") then 1 else 0 end) as n_verified_certified,

                   sum(ndays_act) as ndays_act_sum,
                   sum(nevents) as nevents_sum,
                   sum(nforum_posts) as nforum_posts_sum,
    
                   sum(nshow_answer) as nshow_answer_sum,

                   avg(avg_dt) as avg_of_avg_dt,
                   avg(sum_dt) as avg_of_sum_dt,
                   avg(case when certified then avg_dt else null end) as certified_avg_dt,
                   avg(case when certified then sum_dt else null end) as certified_sum_dt,
                FROM [{dataset}.person_course] 
                WHERE cc_by_ip is not null
                group by cc, countryLabel, course_id
                order by cc
        """.format(dataset=dataset, course_id=course_id)

        table = 'stats_geo0'
        key = None
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key,
                                        depends_on=['%s.person_course' % dataset])


    def compute_overall_enrollment_by_day(self):
        '''
        Compute enrollment by day from enrollday_sql, over all courses
        '''
        sql = """
           SELECT  date,
                   sum(nregistered_ever) as nregistered_ever_sum,
                   sum(nregistered_ever_sum) over (order by date) as nregistered_ever_cum,

                   sum(nregistered_net) as nregistered_net_sum,
                   sum(nregistered_net_sum) over (order by date) as nregistered_net_cum,

                   sum(nverified_ever) as nverified_ever_sum,
                   sum(nverified_ever_sum) over (order by date) as nverified_ever_cum,

                   sum(nverified_net) as nverified_net_sum,
                   sum(nverified_net_sum) over (order by date) as nverified_net_cum,

                FROM [course_report_latest.enrollday_sql] 
                group by date
                order by date
        """

        dataset = "course_report_latest"
        table = 'stats_overall_enrollment'
        key = None
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key,
                                        depends_on=['course_report_latest.enrollday_sql'])


    def get_sm_nuser_views(self, module_id):
        return self.bqdata['stats_module_usage']['data_by_key'].get('i4x://' + module_id, {}).get('ncount', '')
    

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


    def load_course_axis(self, course_id, dtype='data_by_key'):
        '''
        Get course axis table from BQ.  Use memcache.

        The course axis has these fields:

        category, index, url_name, name, gformat, due, start, module_id, course_id, path, data.ytid, data.weight, chapter_mid
        '''
        dataset = bqutil.course_id2dataset(course_id, use_dataset_latest=self.USE_LATEST)
        table = "course_axis"
        key={'name': 'url_name'}
        # return self.cached_get_bq_table(dataset, table, key=key, drop=['data'])['data_by_key']
        return self.cached_get_bq_table(dataset, table, key=key)[dtype]


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

    def get_course_listings(self):

        all_courses = self.get_data(local_config.COURSE_LISTINGS_TABLE, key={'name': 'course_id'})

        courses = {'data': [], 'data_by_key': OrderedDict()}

        for course_id, cinfo in all_courses['data_by_key'].items():
            if not self.is_user_authorized_for_course(course_id):
                continue
            courses['data'].append(cinfo)
            courses['data_by_key'][course_id] = cinfo

        for k in courses['data']:
            cid = k['course_id']
            if not cid:
                logging.info('oops, bad course_id! line=%s' % k)
                continue
            if ('course_number' not in k) and ('Course Number' in k):
                k['course_number'] = k['Course Number']	# different conventions for BigQuery and Google Spreadsheet
                
            k['course_image'] = self.get_course_image(cid)
            try:
                k['title'] = unidecode(k.get('title', k.get('Title'))).encode('utf8')
            except:
                logging.error('[get_course_listings] oops, cannot encode title, row=%s' % k)
                raise
            (m,d,y) = map(int, k.get('courses_launch', k.get('Course Launch', '')).split('/'))
            ldate = "%04d-%02d-%02d" % (y,m,d)
            k['launch'] = ldate
            courses['data_by_key'][cid]['launch'] = ldate
        return courses

    @staticmethod
    def fix_date(x):
        if x:
            return str(datetime.datetime.utcfromtimestamp(float(x)))
        return ''

    @staticmethod
    def datetime2milliseconds(dt=None, dtstr=''):
        '''
        Return datetime as milliseconds from epoch (js convention)
        dtstr may be YYYY-MM-DD
        '''
        dtstr = dtstr.strip()
        if dt is None and not dtstr:
            return None
        if dtstr:
            try:
                if '-' in dtstr:
                    (y,m,d) = map(int, dtstr.split('-'))
                elif '/' in dtstr:
                    (m,d,y) = map(int, dtstr.split('/'))
                else:
                    y = int(dtstr[:4])
                    m = int(dtstr[4:6])
                    d = int(dtstr[6:])
                    (m,d,y) = map(int, dtstr.split('/'))
            except Exception as err:
                logging.error("[datetime2milliseconds] cannot parse %s, err=%s" % (dtstr, err))
                return None
            dt = datetime.datetime(y,m,d)
        return (dt - datetime.datetime(1970, 1, 1)).total_seconds() * 1000

    def get_report_geo_stats(self):
        table = 'geographic_distributions'
        dataset = 'course_report_latest'
        return self.cached_get_bq_table(dataset, table)
        
    def get_report_broad_stats(self):
        table = 'broad_stats_by_course'
        dataset = 'course_report_latest'
        key = None
        tableinfo = bqutil.get_bq_table_info(dataset, table)
        data = self.cached_get_bq_table(dataset, table, key=key)
        return (data, tableinfo)
