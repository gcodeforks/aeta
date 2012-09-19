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

"""Models used by aeta."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

# Classes defined here are only data containers - pylint:disable-msg=R0903

import unittest

__all__ = ['ModuleData', 'TestResultData']


class ModuleData(object):
  """Description of a test module."""

  def __init__(self, fullname, tests=None, load_error=False,
               load_traceback=None):
    if not isinstance(fullname, str):
      raise TypeError('"fullname" must be a string, not a %s' %
                      type(fullname))
    # full module name
    self.fullname = fullname
    # key = test class name; value = list of test methods
    if tests is not None:
      self.tests = tests
    else:
      self.tests = {}
    # Error which occured while loading this module. None if no error occured.
    self.load_error = load_error
    # Traceback string of an occur if it occured. None if no error occured.
    self.load_traceback = load_traceback


class TestResultData(object):
  """TestResult information."""

  def __init__(self, testresult, fullname):
    if not isinstance(testresult, unittest.TestResult):
      raise TypeError('"testresult" must be unittest.TestResult, not a %s' %
                      type(testresult))
    if not isinstance(fullname, str):
      raise TypeError('"fullname" must be a string, not a %s' %
                      type(fullname))
    self.fullname = fullname
    # Tuples of (testcase, exceptioninfo) for unexpected exceptions.
    self.errors = testresult.errors
    # Tuples of (testcase, exceptioninfo) for failed tests.
    self.failures = testresult.failures
    # Total number of tests run.
    # pylint: disable-msg=C0103
    self.testsRun = testresult.testsRun
    # output of entire test run
    self.output = ''

  # simple property - pylint:disable-msg=C0111
  @property
  def passed(self):
    return not self.errors + self.failures
