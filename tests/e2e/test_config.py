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

"""Tests for the configuration of aeta."""



# Disable checking; pylint: disable-msg=C0111,W0212,R0904,C0103
# - docstrings
# - access to protected members
# - too many public methods
# - setUp() and tearDown() method names

import unittest

from aeta import config


class DefaultConfigTest(unittest.TestCase):
  """Test cases for aeta configuration."""

  def setUp(self):
    self.config = config.get_config()

  def testDefaults(self):
    # url_path dynamically assigned - pylint:disable-msg=E1101
    self.assertEqual('/tests/', self.config.url_path)
    self.assertEqual('^test_[\w]+$', self.config.test_module_pattern)

  def test_customs(self):
    # test_package_names dynamically assigned - pylint:disable-msg=E1101
    self.assertEqual(['unit_and_e2e_tests', 'e2e_tests'],
                     self.config.test_package_names)
