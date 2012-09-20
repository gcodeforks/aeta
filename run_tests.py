#!/usr/bin/python
# Copyright 2013 Google Inc. All Rights Reserved.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Script to run tests."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

import optparse
import os
import sys

from aeta import local_client
import gaedriver
import unittest2

USAGE = """%prog [unit|e2e|all]"""


ROOT_PATH = os.path.abspath(os.path.dirname(__file__))


# Relative directory for unit tests.
UNIT_TEST_DIRS = [os.path.join('tests', 'unit'),
                  os.path.join('tests', 'unit_and_e2e')]

# Relative directory for Python 2.5 end-to-end test application.
E2E_TEST_25_APP_DIR = os.path.abspath(os.path.join('testdata', 'e2e_25_app'))

# Relative directory for Python 2.7 end-to-end test application.
E2E_TEST_27_APP_DIR = os.path.abspath(os.path.join('testdata', 'e2e_27_app'))

# Hostname fed to gaedriver for e2e tests.
E2E_HOSTNAME = 'localhost:8087'


def run_unit_tests():
  suite = unittest2.TestSuite()
  for unit_test_dir in UNIT_TEST_DIRS:
    absolute_test_dir = os.path.join(ROOT_PATH, unit_test_dir)
    suite = unittest2.loader.TestLoader().discover(absolute_test_dir)
    unittest2.TextTestRunner(verbosity=2).run(suite)


def run_e2e_tests(sdk_dir):
  if not sdk_dir:
    raise ValueError('"--sdk_dir" must be provided for e2e tests.')
  for app_dir in [E2E_TEST_25_APP_DIR, E2E_TEST_27_APP_DIR]:
    config = gaedriver.Config(app_id='aeta-e2e-test',
                              app_dir=app_dir,
                              cluster_hostname=E2E_HOSTNAME,
                              sdk_dir=sdk_dir)
    app_token = gaedriver.setup_app(config)
    aeta_url = 'http://%s/tests' % config.app_hostname
    local_client.main(aeta_url)
    gaedriver.teardown_app(config, app_token)


def main(test_size):
  sdk_dir = os.getenv('AETA_SDK_DIR')
  if not sdk_dir:
    print 'You must run "source init-dev-env.sh" first.'
    sys.exit(1)
  if test_size == 'unit':
    run_unit_tests()
  elif test_size == 'e2e':
    run_e2e_tests(sdk_dir)
  elif test_size == 'all':
    run_unit_tests()
    run_e2e_tests(sdk_dir)
  else:
    print 'Say what? Expected test size is either "unit", "e2e", or "all".'
    sys.exit(1)


if __name__ == '__main__':
  PARSER = optparse.OptionParser(USAGE)
  OPTIONS, ARGS = PARSER.parse_args()
  if len(ARGS) != 1:
    print 'Error: Exactly 1 arguments required.'
    PARSER.print_help()
    sys.exit(1)
  TEST_SIZE = ARGS[0]
  main(TEST_SIZE)
