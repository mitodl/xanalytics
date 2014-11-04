#
# python functions which compute statistics tables (no views)
#
# This produces much of the data to be obtained via AJAX calls, but the
# AJAX calls themselves should go elsewhere.
#

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
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key)

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
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key)


    def compute_enrollment_by_day(self, course_id, start="2012-08-20", end="2015-01-01"):
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

        # special handling: use new enrollday2_* tables if available, instead of enrollday_* 
        tables = bqutil.get_list_of_table_ids(input_dataset)
        prefixes = [x.split('_')[0] for x in tables]
        if 'enrollday2' in prefixes:
            sql = sql_enrollday2
            logging.info('[compute_enrollment_by_day] using enrollday2 for %s' % course_id)
        else:
            sql = sql_enrollday

        table = 'stats_enrollment_by_day'
        key = None
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key,
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

        table = 'stats_activity_by_day'
        key = None
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key,
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
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key)


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
        return self.cached_get_bq_table(dataset, table, sql=sql, key=key)


    def cached_get_bq_table(self, dataset, table, sql=None, key=None, drop=None,
                            logger=None, ignore_cache=False):
        '''
        Get a dataset from BigQuery; use memcache
        '''
        if logger is None:
            logger = logging.info
        memset = '%s.%s' % (dataset,table)
        data = mem.get(memset)
        if (not data) or ignore_cache:
            try:
                data = bqutil.get_bq_table(dataset, table, sql, key=key, logger=logger)
            except Exception as err:
                logging.error(err)
                data = {'fields': {}, 'field_names': [], 'data': [], 'data_by_key': {}}
                return data		# don't cache empty result
            if (drop is not None) and drop:
                for key in drop:
                    data.pop(key)	# because data can be too huge for memcache ("Values may not be more than 1000000 bytes in length")
            try:
                mem.set(memset, data, time=3600*12)
            except Exception as err:
                logging.error('error doing mem.set for %s.%s from bigquery' % (dataset, table))
        self.bqdata[table] = data
        return data

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

    def get_sm_nuser_views(self, module_id):
        return self.bqdata['stats_module_usage']['data_by_key'].get('i4x://' + module_id, {}).get('ncount', '')
    
