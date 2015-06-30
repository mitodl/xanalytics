import re
import logging
import json
import webapp2
import cloudstorage as gcs
import local_config
import unicodecsv as csv

from google.appengine.api import app_identity
import auth
from auth import auth_required, auth_and_role_required
from templates import JINJA_ENVIRONMENT
from datasource import DataSource
from stats import DataStats
from collections import OrderedDict

# for local dev debugging, use "gsutil -d ls" and copy str after "Bearer"
# gcs.common.set_access_token("ya...")

class FileStoragePages(auth.AuthenticatedHandler, DataStats, DataSource):
    '''
    Provide access to files in google cloud storage, stored
    using the convention of directories named by course_id.replace('/', '__').
    
    Limit access to content in the "DIST" subdirectory of the course directory.
    '''
    def course_bucket(self, course_id, filename=None, ddir="/DIST"):
        try:
            gs_bucket = local_config.GOOGLE_STORAGE_ROOT
        except Exception as err:
            gs_bucket = app_identity.get_default_gcs_bucket_name()
        gsfp = "/%s/%s%s" % (gs_bucket, course_id.replace('/', '__'), ddir)
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
        return self.list_files_available_in_bucket(bucket, fn_filter)

    @auth_and_role_required(role='pm')
    @auth_required
    def ajax_list_report_files(self):
        '''
        Return json with list of files avilable in reports
        '''
        if not self.user in self.AUTHORIZED_USERS:	# require superuser
            return self.no_auth_sorry()

        cr_dir = self.get_course_report_dataset()
        bucket = self.course_bucket(cr_dir, ddir="")
        return self.list_files_available_in_bucket(bucket)

    @auth_required
    def list_files_available_in_bucket(self, bucket, fn_filter=None):
        files = []
        logging.info("list bucket = %s" % bucket)
        # logging.info("gcs access token = %s" % gcs.common.get_access_token())
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

    @auth_required
    def ajax_get_report(self, filename=None, group_tag=None, course_id=None):
        '''
        Return JSON of data from specified CSV file.  Only include courses which have a matching tag
        (in the "tags" column of the course listings) or course_id.  Control access based on group_tag
        and / or course_id.

        The file must be in the course_report or course_report_latest bucket.
        '''
        filename = self.request.get('filename', None)
        if not filename:
            self.response.headers['Content-Type'] = 'application/json'   
            self.response.out.write({"error": "No filename specified"})
            return
        if not filename.endswith('.csv'):
            self.response.headers['Content-Type'] = 'application/json'   
            self.response.out.write({"error": "Only CSV files can be specified"})
            return
        
        group_tag = group_tag or self.request.get('group_tag', None)
        course_id = course_id or self.request.get('course_id', None)

        if not group_tag:
            if not course_id:
                if not self.does_user_have_role('pm'):
                    return self.no_auth_sorry()
            else:
                if not self.is_user_authorized_for_course(course_id):
                    return self.no_auth_sorry()
        else:
            if not self.is_user_authorized_for_course(group_tag):
                return self.no_auth_sorry()

        if group_tag:
            courses = self.get_course_listings(check_individual_auth=False)
            known_course_ids_with_tags = {x['course_id']: x.get('tags', None) for x in courses['data']}
        else:
            known_course_ids_with_tags = {course_id: None}

        try:
            cr_dir = self.get_course_report_dataset()
            bucket = self.course_bucket(cr_dir, filename, ddir="")
            gcs_file = gcs.open(bucket)
            data_by_cid = OrderedDict()

            for row in csv.DictReader(gcs_file):
                if not 'course_id' in row:
                    self.response.headers['Content-Type'] = 'application/json'   
                    self.response.out.write({"error": "CSV file missing course_id column"})
                    return
                cid = row['course_id']
                if not cid in known_course_ids_with_tags:
                    continue
                if group_tag:
                    course_tags = known_course_ids_with_tags[cid]
                    if not self.course_listings_row_has_tag(course_tags, group_tag):
                        continue
                data_by_cid[cid] = row
                
            self.response.write(json.dumps(data_by_cid))
            gcs_file.close()
        except Exception as err:
            self.response.headers['Content-Type'] = 'application/json'   
            self.response.out.write({"error": str(err)})
            return

FileStorageRoutes = [
# ajax routes
    webapp2.Route('/file/list/course/<org>/<number>/<semester>', handler=FileStoragePages, handler_method='ajax_list_files_available'),
    webapp2.Route('/file/get/course/<org>/<number>/<semester>', handler=FileStoragePages, handler_method='ajax_get_file'),
    webapp2.Route('/file/list/report', handler=FileStoragePages, handler_method='ajax_list_report_files'),
    webapp2.Route('/file/get/report', handler=FileStoragePages, handler_method='ajax_get_report'),
]
