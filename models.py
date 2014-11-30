from google.appengine.ext import ndb

class StaffUser(ndb.Model):
    """
    user model
    """
    username = ndb.StringProperty(indexed=True)
    name = ndb.StringProperty(indexed=False, default='')
    role = ndb.StringProperty(indexed=True)
    course_id = ndb.StringProperty(indexed=True)
    notes = ndb.StringProperty(indexed=False, default='')
    enabled = ndb.BooleanProperty(indexed=False, default=True)

class LogLine(ndb.Model):
    """
    access log entry line
    """
    username = ndb.StringProperty(indexed=True)
    created = ndb.DateTimeProperty(indexed=True, auto_now_add=True)
    course_id = ndb.StringProperty(indexed=True)
    url = ndb.StringProperty(indexed=False, default='')
    ipaddr = ndb.StringProperty(indexed=False, default='')

