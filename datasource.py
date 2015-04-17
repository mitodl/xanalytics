#
# backend model for retrieving data, from files, BigQuery, and from ndb
#

import csv
import codecs
import models
import logging

import gsdata
import bqutil
import datetime
import dateutil
import dateutil.parser
from collections import defaultdict, OrderedDict
from google.appengine.api import memcache

mem = memcache.Client()

NDB_DATASETS = {'staff': models.StaffUser,
                'CustomReport': models.CustomReport,
}

class DataSource(object):
    '''
    Methods for retrieving data from files, BigQuery, and from ndb
    '''

    #-----------------------------------------------------------------------------

    def get_data(self, source, key=None, ignore_cache=False):
        '''
        Get data from source, and return.
        source should either be string of the form "dataset.table" specifying a BigQuery source,
        or "docs:file_name:sheet_name" specifying a Google Spreadsheet source.
        '''
        if source.startswith('ndb:'):
            table = source[4:]
            #return self.cached_get_ndb_data(table, ignore_cache=ignore_cache)	# ndb supposed to do its own memcaching
            return self.get_ndb_data(table)

        if source.startswith('docs:'):
            (fname, sheet) = source[5:].split(':',1)
            return gsdata.cached_get_datasheet(fname, sheet, key=key, ignore_cache=ignore_cache)

        if source.startswith('file:'):
            return self.get_datafile(source[5:], key=key)

        (dataset, table) = source.split('.')
        return self.cached_get_bq_table(dataset, table, key=key, ignore_cache=ignore_cache)

    @staticmethod
    def get_ndb_dataset(table):
        if table not in NDB_DATASETS:
            raise Exception("[datasource] Error!  Unknown NDB data set %s" % table)
        return NDB_DATASETS[table]

    def cached_get_ndb_data(self, table, key=None, ignore_cache=False):
        memset = '%s%s' % ('ndb',table)
        data = mem.get(memset)
        if (not data) or ignore_cache:
            data = self.get_ndb_data(table, key=key)
            try:
                mem.set(memset, data, time=60*10)
            except Exception as err:
                logging.error('error doing mem.set for %s from NDB' % (table))
        return data

    def get_ndb_data(self, table, key=None):
        ndbset = self.get_ndb_dataset(table)
        ret = {'data': []}
        entity = None
        for entity in ndbset.query():
            de = { prop : getattr(entity, prop) for prop in entity._properties }
            ret['data'].append(de)
                
        if key is not None:
            ret['data_by_key'] = self.make_data_by_key(ret['data'], key)
                
        if entity is not None:
            ret['fields'] = entity._properties
            ret['field_names'] = ret['fields']
        return ret

    def fix_date_fields(self, data, fields):
        for field in fields:
            dstr = data[field]
            if dstr.count('/')==2:
                (m, d, y) = map(int, dstr.split(' ')[0].split('/'))
                if (y>70):
                    y += 1900
                elif (y<= 70):
                    y += 2000
                data[field] = datetime.datetime(y, m, d)
            elif dstr.count('-')==2 and dstr.count(':')==0:
                (y, m, d) = map(int, dstr.split('/'))
                data[field] = datetime.datetime(y, m, d)
            else:
                try:
                    data[field] = dateutil.parser.parse(dstr)
                except Exception as err:
                    raise Exception('do not know how to parse date time %s, err=%s' % (dstr, err))

    def import_data_to_ndb(self, data, table, overwrite=False, extra_params=None, date_fields=None, overwrite_query=None):
        ndbset = self.get_ndb_dataset(table)

        if overwrite:
            models.ndb.delete_multi([x.key for x in ndbset.query(*(overwrite_query or []))])

        cnt = 0
        for entry in data:

            if date_fields:
                self.fix_date_fields(entry, date_fields)
            entity = ndbset(**entry)
            for key, val in (extra_params or {}).iteritems():	# set extra parameters on each entity
                setattr(entity, key, val)
            entity.put()
            cnt += 1
        return cnt

    def get_datafile(self, fn, key=None):
        '''
        Get data from local csv file, and return.
        '''
        ret = {'data': []}
        with codecs.open('data/' + fn) as fp:
            for cdr in csv.DictReader(fp):
                ret['data'].append(cdr)

        if key is not None:
            ret['data_by_key'] = self.make_data_by_key(ret['data'], key)
                
        ret['fields'] = cdr.keys()
        ret['field_names'] = cdr.keys()
        return ret

    @staticmethod
    def make_data_by_key(data, key):
        if type(key)==dict:
            keyname = key['name']
        else:
            keyname = key
        data_by_key = OrderedDict()
        for row in data:
            the_key = row[keyname]
            if type(key)=='dict' and "keymap" in key:
                the_key = key['keymap'](the_key)
            data_by_key[the_key] = row
        return data_by_key


    def cached_get_bq_table(self, dataset, table, sql=None, key=None, drop=None,
                            logger=None, ignore_cache=False, 
                            depends_on=None,
                            force_query=False,
                            force_newer_than=None,
                            startIndex=0, maxResults=1000000,
                            raise_exception=False,
                            project_id=None,
    ):
        '''
        Get a dataset from BigQuery; use memcache.

        If "depends_on" is provided (as a list of strings), and if the desired table
        already exists, then check to make sure it is newer than any of the tables
        listed in "depends_on".

        if force_newer_than is set (should be a datetime) then in the depends_on
        testing, use that date as an override, such that the SQL is re-run if
        the existing table is older than this date.

        project_id: if specified, overrides the default BigQuery project ID (for the actual query)
        '''
        if logger is None:
            logger = logging.info
        memset = '%s.%s' % (dataset,table)
        if startIndex:
            memset += '-%d-%d' % (startIndex, maxResults)
        data = mem.get(memset)

        optargs = {}
        if project_id:
            optargs['project_id'] = project_id

        if depends_on is not None:
            # get the latest mod time of tables in depends_on:
            modtimes = [ bqutil.get_bq_table_last_modified_datetime(*(x.split('.',1)), **optargs) for x in depends_on]
            latest = max([x for x in modtimes if x is not None])
            
            if not latest:
                raise Exception("[datasource.cached_get_bq_table] Cannot get last mod time for %s (got %s), needed by %s.%s" % (depends_on, modtimes, dataset, table))

            if force_newer_than and force_newer_than > latest:
                latest = force_newer_than

            if data and data.get('lastModifiedTime', None):
                # data has a mod time, let's see if that has expired
                if data.get('lastModifiedTime', None) < latest:
                    ignore_cache = True

            # get the mod time of the computed table, if it exists
            try:
                table_date = bqutil.get_bq_table_last_modified_datetime(dataset, table)
            except Exception as err:
                if 'Not Found' in str(err):
                    table_date = None
                    ignore_cache = True
                    logging.info("[datasource.cached_get_bq_table] Table %s.%s doesn't exist, forcing recomputation" % (dataset, table))
                else:
                    raise

            if table_date and table_date < latest:
                ignore_cache = True
                if sql:
                    force_query = True
                    logging.info("[datasource.cached_get_bq_table] Forcing query recomputation of %s.%s, table_date=%s, latest=%s" % (dataset, table,
                                                                                                                                      table_date, latest))
                else:
                    logging.info("[datasource.cached_get_bq_table] Forcing cache reload of %s.%s, table_date=%s, latest=%s" % (dataset, table,
                                                                                                                               table_date, latest))

            # logging.info("[datasource.cached_get_bq_table] %s.%s table_date=%s, latest=%s, force_query=%s" % (dataset, table, table_date, latest, force_query))

        if (not data) or ignore_cache or (not data['data']):	# data['data']=None if table was empty, and in that case try again
            try:
                data = bqutil.get_bq_table(dataset, table, sql, key=key, logger=logger,
                                           force_query=force_query,
                                           startIndex=startIndex, 
                                           maxResults=maxResults, **optargs)
            except Exception as err:
                logging.error(err)
                if raise_exception:
                    raise
                data = {'fields': {}, 'field_names': [], 'data': [], 'data_by_key': {}}
                return data		# don't cache empty result
            data['depends_on'] = depends_on
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
