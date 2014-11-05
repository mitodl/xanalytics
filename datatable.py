
class DataTableField(object):
    '''
    Info container for javascript datatable field labels and names.
    
    Initialize with field being a string (simple case), or a dict, with entries:

    field = data dict key for this data column
    title = title to display for data column (optional)
    width = percentage width for data column (optional)
    icon = special indicator of graphical icon, e.g. "delete"
    '''
    def __init__(self, field):
        if type(field)==DataTableField:
            field = field.field_in
        self.field_in = field
        self.title = str(field)
        self.field = str(field)
        self.width = None
        self.fmtclass = None
        self.icon = None

        if type(field)==dict:
            self.icon = field.get('icon', None)
            self.field = field.get('field', None)
            self.title = field.get('title', self.field)
            self.width = field.get('width', None)
            self.fmtclass = field.get('class', None)
    def __str__(self):
        return self.title
    def colinfo(self):
        ci = {'data': self.field}
        if self.fmtclass is not None:
            ci['className'] = self.fmtclass
        return ci
