import os
import json
import gspread
import logging
from httplib2 import Http
import local_config

from oauth2client.client import flow_from_clientsecrets, Credentials
try:
    from oauth2client.client import SignedJwtAssertionCredentials
except:
    from oauth2client.service_account import ServiceAccountCredentials

if hasattr(local_config, "GSPREAD_SERVICE_KEY_FILE"):
    logging.info("[auth_gspread] loading auth from service key file")
    mydir = os.path.abspath(os.path.dirname(__file__))
    SERVICE_KEY_FILE = "%s/%s" % (mydir, local_config.GSPREAD_SERVICE_KEY_FILE)
    with open(SERVICE_KEY_FILE) as f:
        data = json.loads(f.read())
    private_key = data['private_key']
    SERVICE_EMAIL = data['client_email']

    scope = ['https://spreadsheets.google.com/feeds',
             'https://www.googleapis.com/auth/drive']
    try:
        credentials = SignedJwtAssertionCredentials(SERVICE_EMAIL, private_key, scope)
    except Exception as err:
        print("Warning: %s" % str(err))
        credentials = ServiceAccountCredentials.from_p12_keyfile(SERVICE_EMAIL, SERVICE_KEY_FILE.replace('.pem', '.p12'), scopes=scope)
    logging.info("[auth_gspread] loaded auth from service key, credentials=%s" % str(credentials))
    
