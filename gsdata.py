#
# File:   gsdata.py
# Date:   03-Nov-14
# Author: I. Chuang <ichuang@mit.edu>
#
# retrieve data from google spreadsheet, using service account

import sys
import time
import json
import gspread
import logging
import local_config
from collections import OrderedDict

from oauth2client.appengine import AppAssertionCredentials
from google.appengine.api import memcache

mem = memcache.Client()

SCOPE = 'https://spreadsheets.google.com/feeds https://docs.google.com/feeds'
# logging.info('credentials = ', credentials)

def cached_get_datasheet(fname, sheet, key=None, ignore_cache=False):
    memset = 'docs:%s.%s' % (fname, sheet)
    data = mem.get(memset)
    if (not data) or ignore_cache:
        cnt = 0
        data = None
        while (cnt < 10):
            try:
                data = get_datasheet(fname, sheet, key)
                if cnt:
                    cnt += 1
                    logging.error('[gsdata.cached_get_dataset] (attempt=%d) succeeded getting %s.%s' % (cnt, fname, sheet))
                break
            except Exception as err:
                cnt += 1
                logging.error('[gsdata.cached_get_dataset] (attempt %d) failed getting %s.%s, err=%s' % (cnt, fname, sheet, err))
                time.sleep(0.2)
        if data is None:
            msg = '[gsdata.cached_get_dataset] failed getting %s.%s!' % (fname, sheet)
            logging.error(msg)
            raise Exception(msg)
        try:
            mem.set(memset, data, time=3600*12)
        except Exception as err:
            logging.error('error doing mem.set for %s.%s from google spreadsheet' % (fname, sheet))
    return data

def get_worksheet(fname, sheet):
    credentials = AppAssertionCredentials(scope=SCOPE)
    gc = gspread.authorize(credentials)

    try:
        wks = gc.open(fname).worksheet(sheet)
    except Exception as err:
        logging.error("[get_datasehet] oops, failure getting fname=%s, sheet=%s" % (fname, sheet))
        raise
    return wks

def get_datasheet(fname, sheet, key=None):
    '''
    Get data from google spreadsheet file name "fname", sheet name "sheet"
    For compatibility with bqutil, return a dict, with

    field_names = name of top-level schema fields
    fields = same as field_names (fixme)
    data = list of data
    data_by_key = dict of data, with key being the value of the fieldname specified as the key arg

    Assumes first row of spreadsheet is keys to data in rows.
    '''
    wks = get_worksheet(fname, sheet)
    lol = wks.get_all_values()
    fields = lol[0]

    data = []
    for row in lol[1:]:
        data.append(dict(zip(fields, row)))

    ret = {'data': data, 'fields': fields, 'field_names': fields}
    
    if key is not None:
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
        ret['data_by_key'] = data_by_key

    # logging.error('[gsdata] ret=%s' % json.dumps(ret, indent=4))
    return ret
           
def modify_datasheet_acell(fname, sheet, entry, newval):
    '''
    change spcified spreadsheet entry to newval
    '''
    wks = get_worksheet(fname, sheet)
    wks.update_acell(entry, newval)
    
def append_row_to_datasheet(fname, sheet, newrow):
    '''
    append row to spreadsheet
    '''
    wks = get_worksheet(fname, sheet)
    wks.append_row(newrow)

def insert_row_in_datasheet(fname, sheet, newpos, newrow):
    '''
    insert row in spreadsheet
    '''
    wks = get_worksheet(fname, sheet)
    wks.insert_row(newrow, index=newpos)
