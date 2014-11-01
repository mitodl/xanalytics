#!/usr/bin/python
import optparse
import sys
import unittest

def main(sdk_path, test_path):
    sys.path.insert(0, sdk_path)
    import dev_appserver
    dev_appserver.fix_sys_path()
    suite = unittest.loader.TestLoader().discover(test_path)
    unittest.TextTestRunner(verbosity=2).run(suite)


if __name__ == '__main__':
    parser = optparse.OptionParser('')
    options, args = parser.parse_args()
    SDK_PATH = "/usr/local/google_appengine"
    TEST_PATH = "./tests"
    #TEST_PATH = "."
    main(SDK_PATH, TEST_PATH)
