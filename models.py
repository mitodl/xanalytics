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


class CustomReport(ndb.Model):
    """
    Custom report metadata
    """
    name = ndb.StringProperty(indexed=True)		# name should be unique
    author = ndb.StringProperty(indexed=True)
    title = ndb.StringProperty(indexed=False)
    description = ndb.StringProperty(indexed=False)
    table_name = ndb.StringProperty(indexed=True)
    collection = ndb.StringProperty(indexed=True)
    date = ndb.DateTimeProperty(indexed=True, auto_now_add=True)
    sql = ndb.StringProperty(indexed=False)
    depends_on = ndb.StringProperty(indexed=False)	# JSON of list of strings
    html = ndb.StringProperty(indexed=False)
    javascript = ndb.StringProperty(indexed=False)
    icon = ndb.StringProperty(indexed=False)
    group_tags = ndb.StringProperty(indexed=True, repeated=True)	# which pages it's on; also used for access control

    
