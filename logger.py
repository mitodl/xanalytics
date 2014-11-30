from google.appengine.ext import ndb
from models import LogLine

def LogAccess(username, request, course_id=None):
    '''
    Write a log entry line
    '''
    ll = LogLine(username=username, 
                 course_id=course_id, 
                 url=request.url,
                 ipaddr=request.remote_addr)
    ll.put()

def GetRecentLogLines(nlast=10):
    '''
    Return last nlast entries in access log
    '''
    ret = LogLine.query().order(-LogLine.created).fetch(nlast)
    return ret
