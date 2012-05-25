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

"""Tests for the models module of aeta."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

# Disable checking; pylint: disable-msg=C0111,W0212,R0904,C0103
# - docstrings
# - access to protected members
# - too many public methods
# - setUp() and tearDown() method names

import unittest

from aeta import models


class ModuleDataTest(unittest.TestCase):
  """Tests for the ModuleData class."""

  def test_constructor_wrong_input(self):
    self.assertRaises(TypeError, models.ModuleData, None)
    self.assertRaises(TypeError, models.ModuleData, [])

  def test_constructor_correct_input_basic(self):
    fullname = 'package.subpackage.module'
    data = models.ModuleData(fullname)
    self.assertEqual(fullname, data.fullname)
    self.assertEqual({}, data.tests)
    self.assertEqual(False, data.load_error)
    self.assertEqual(None, data.load_traceback)

  def test_constructor_correct_input_full(self):
    fullname = 'package.subpackage.module'
    tests_dummy = {'foo': 'bar'}
    traceback_dummy = 'lispum orium'
    data = models.ModuleData(fullname, tests=tests_dummy, load_error=True,
                             load_traceback=traceback_dummy)
    self.assertEqual(fullname, data.fullname)
    self.assertEqual(tests_dummy, data.tests)
    self.assertEqual(True, data.load_error)
    self.assertEqual(traceback_dummy, data.load_traceback)


class TestResultDataTest(unittest.TestCase):
  """Tests for the TestResultData class."""

  def setUp(self):
    self.testresult = unittest.TestResult()
    self.fullname = 'package.subpackage.module'

  def test_constructor_wrong_input(self):
    self.assertRaises(TypeError, models.TestResultData, None, None)
    self.assertRaises(TypeError, models.TestResultData, self.testresult, None)
    self.assertRaises(TypeError, models.TestResultData, None, self.fullname)

  def test_constructor_correct_cnput(self):
    data = models.TestResultData(self.testresult, self.fullname)
    self.assertEqual(self.fullname, data.fullname)
    self.assertEqual(self.testresult.errors, data.errors)
    self.assertEqual(self.testresult.failures, data.failures)
    self.assertEqual(self.testresult.testsRun, data.testsRun)
    self.assertEqual('', data.output)

  def test_has_passed_no_errors_no_failures(self):
    data = models.TestResultData(self.testresult, self.fullname)
    self.assertEqual(True, data.passed)

  def test_has_passed_with_error(self):
    self.testresult.errors = [('fake', 'content')]
    data = models.TestResultData(self.testresult, self.fullname)
    self.assertEqual(False, data.passed)

  def test_has_passed_with_failures(self):
    self.testresult.failures = [('fake', 'content')]
    data = models.TestResultData(self.testresult, self.fullname)
    self.assertEqual(False, data.passed)
