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

"""This module contains a test that relies on class-level test fixtures."""

import sys
import unittest


class HasClassFixture(unittest.TestCase):
  """Example test case class with a setUpClass method."""

  @classmethod
  def setUpClass(cls):
    cls.class_value = 'something'

  def test_has_class_value(self):
    version_string = '%s.%s'% (sys.version_info[0], sys.version_info[1])
    if version_string < '2.7':
      return
    self.assertEqual('something',
                     getattr(HasClassFixture, 'class_value', None))

  def test_has_bad_class_value(self):
    self.assertEqual('something else',
                     getattr(HasClassFixture, 'class_value', None),
                     msg='This test is expected to fail.')


class HasNoClassFixture(unittest.TestCase):

  def test_pass(self):
    self.assertEqual(1, 1)

  def test_fail(self):
    self.assertEqual(1, 2, msg='This test is expected to fail.')
