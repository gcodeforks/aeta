# Copyright 2012 Google Inc. All Rights Reserved.

# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at

#     http://www.apache.org/licenses/LICENSE-2.0

# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""This module contains a test that relies on module-level test fixtures.

Note that this is only relevant for Python versions >= 2.7. Previous versions
do not support this functionality.
"""



import sys
import unittest

# A test variable used to test module-level setup.
module_test_variable = None

# Hint that indicates setUpModule() was called.
SETUP_MODULE_HINT = 'setUpModule was called'


def setUpModule():
  global module_test_variable
  module_test_variable = SETUP_MODULE_HINT


def tearDownModule():
  global module_test_variable
  module_test_variable = None


class ModuleFixtureTestCase(unittest.TestCase):
  """A test to verify that module-fixture methods are called.

  Note that we only check setUpModule() as tearDownModule is more difficult
  with the current setup. But since we rely on the unit testing framework here
  anyway it is okay to assume that if the setup method was called, the teardown
  method will be as well.
  """

  def test_setup_module_called(self):
    version_string = '%s.%s' % (sys.version_info[0], sys.version_info[1])
    if version_string < '2.7':
      return
    error_msg = ('expected "module_test_variable" to be "%s, not "%s"' %
                 (SETUP_MODULE_HINT, module_test_variable))
    self.assertEqual(SETUP_MODULE_HINT, module_test_variable, error_msg)

  def test_pass(self):
    pass
