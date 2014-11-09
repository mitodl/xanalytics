# run with py.test

if 1:
    from google.appengine.ext import testbed
    from google.appengine.api.app_identity import app_identity_stub
    from google.appengine.api.app_identity import app_identity_keybased_stub
    import local_config
    email_address = local_config.SERVICE_EMAIL
    private_key_path = local_config.SERVICE_KEY_FILE
    stub = app_identity_keybased_stub.KeyBasedAppIdentityServiceStub(email_address=email_address,
                                                                     private_key_path=private_key_path)
    testbed = testbed.Testbed()
    APP_IDENTITY_SERVICE_NAME = 'app_identity_service'
    testbed.activate()
    #testbed._register_stub(testbed.APP_IDENTITY_SERVICE_NAME, stub)
    testbed._register_stub(APP_IDENTITY_SERVICE_NAME, stub)
    testbed.init_datastore_v3_stub()
    testbed.init_memcache_stub()
    testbed.init_urlfetch_stub()

    from google.appengine.ext import testbed
    testbed = testbed.Testbed()
    testbed.activate()
    testbed.init_datastore_v3_stub()
    testbed.init_memcache_stub()

from bqutil import *

