from google.appengine.ext import ndb

class StaffUser(ndb.Model):
    """
    user model
    """
    username = ndb.StringProperty(indexed=True)
    role = ndb.StringProperty(indexed=True)
    course_id = ndb.StringProperty(indexed=True)
    notes = ndb.StringProperty(indexed=False, default='')
    enabled = ndb.BooleanProperty(indexed=False, default=True)

