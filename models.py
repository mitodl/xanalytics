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
    icon = ndb.StringProperty(indexed=False)		# graphical icon, either as a URL, or a data-encoded URI
    group_tags = ndb.StringProperty(indexed=True, repeated=True)	# which pages it's on; also used for access control
    meta_info = ndb.JsonProperty()		# meta info, including location on page, type of report (e.g. HTML page)
    
    # defined group_tag values:
    #
    # course   - require course_id
    # group    - require group_tag
    # role:pm  - require role "PM" (project manager)
    # role:XXX - require role XXX 
    # open     - anyone can access
    # instructor - require user to be instructor of specified course (pm not sufficient)

    # defined meta_info keys:
    #
    # embedded - true makes this report render immediately with no title or description, embedded into html page
    # is_page  - true makes this report render as its own separate HTML page
    # require_table - provide table name or dataset.table ; if this doesn't exist, then the custom report is not shown
