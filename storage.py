import re
import logging
import json
import webapp2
import cloudstorage as gcs
import local_config

from google.appengine.api import app_identity
import auth
from auth import auth_required, auth_and_role_required
from templates import JINJA_ENVIRONMENT
from stats import DataStats

class FileStoragePages(auth.AuthenticatedHandler, DataStats):
    '''
    Provide access to files in google cloud storage, stored
    using the convention of directories named by course_id.replace('/', '__').
    
    Limit access to content in the "DIST" subdirectory of the course directory.
    '''
    def course_bucket(self, course_id, filename=None):
        try:
            gs_bucket = local_config.GOOGLE_STORAGE_ROOT
        except Exception as err:
            gs_bucket = app_identity.get_default_gcs_bucket_name()
        gsfp = "/%s/%s/DIST" % (gs_bucket, course_id.replace('/', '__'))
        if filename:
            gsfp += "/" + filename
        return gsfp

    def test_create(self):
        filename = "/" + app_identity.get_default_gcs_bucket_name() + "/test1.dat"
        logging.info("creating %s" % filename)
        gcs_file = gcs.open(filename,
                            'w',
                            content_type='text/plain',
                            options={'x-goog-meta-foo': 'foo',
                                     'x-goog-meta-bar': 'bar'}
                        )
        gcs_file.write('abcde\n')
        gcs_file.write('f'*1024*4 + '\n')
        gcs_file.close()
        logging.info("done creating")
        
    @auth_required
    def ajax_list_files_available(self, org=None, number=None, semester=None):
        '''
        Return json with list of files avilable for specified course
        '''
        course_id = '/'.join([org, number, semester])

        bucket = self.course_bucket(course_id)
        fn_filter = self.request.get('filter', None)

        files = []
        logging.info("list bucket = %s" % bucket)
        #for stat in gcs.listbucket(bucket + '/b', delimiter='/'):
        for stat in gcs.listbucket(bucket):
            fn = stat.filename
            fn = re.sub('^%s/' % bucket, '', fn)
            if fn_filter:
                if not re.match(fn_filter, fn):
                    continue
            files.append(fn)
            # logging.info("   --> %s" % stat)
        self.response.headers['Content-Type'] = 'application/json'   
        self.response.out.write(json.dumps(files))

    @auth_required
    def ajax_get_file(self, org=None, number=None, semester=None):
        course_id = '/'.join([org, number, semester])

        filename = self.request.get('filename', None)
        if not filename:
            self.response.headers['Content-Type'] = 'application/json'   
            self.response.out.write({"error": "No filename specified"})
            return
        
        try:
            bucket = self.course_bucket(course_id, filename)
            gcs_file = gcs.open(bucket)

            self.response.write(gcs_file.read())
            gcs_file.close()
        except Exception as err:
            self.response.headers['Content-Type'] = 'application/json'   
            self.response.out.write({"error": str(err)})
            return

FileStorageRoutes = [
# ajax routes
    webapp2.Route('/file/list/course/<org>/<number>/<semester>', handler=FileStoragePages, handler_method='ajax_list_files_available'),
    webapp2.Route('/file/get/course/<org>/<number>/<semester>', handler=FileStoragePages, handler_method='ajax_get_file'),
]
