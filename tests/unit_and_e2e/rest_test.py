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

"""Unit tests for the rest module of aeta."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

# Disable checking; pylint:disable-msg=C0111,W0212,R0904,C0103
# - docstrings
# - access to protected members
# - too many public methods
# - setUp() and tearDown() method names

import unittest

import simplejson as json

from aeta import config
from aeta import logic
from aeta import models
from aeta import rest
from tests import utils

utils.TestDataMixin().setup_test_data()

# special test data setup - pylint:disable-msg=F0401
import sample_package
from sample_package import one_testcase_test

SAMPLE_PACKAGENAME = sample_package.__name__
SAMPLE_SUBPACKAGENAME = '%s.subpackage' % SAMPLE_PACKAGENAME
SAMPLE_MODULENAME = one_testcase_test.__name__
SAMPLE_CLASSNAME = '%s.%s' % (SAMPLE_MODULENAME, 'SimpleTestCase')
SAMPLE_METHODNAME = '%s.%s' % (SAMPLE_CLASSNAME, 'test_pass')


class ConvertModuleDataTest(unittest.TestCase):
  """Tests for the convert_module_data function."""

  def setUp(self):
    self.modtests = {'testcase1': ['testMethod1', 'testMethod2']}
    self.moddata = models.ModuleData(fullname='package.module',
                                     tests=self.modtests,
                                     load_error=False,
                                     load_traceback=None)

  def test_invalid_input(self):
    self.assertRaises(TypeError, rest.convert_module_data, None)
    self.assertRaises(TypeError, rest.convert_module_data, '')
    self.assertRaises(TypeError, rest.convert_module_data, 5)

  def test_valid_input(self):
    json_string = rest.convert_module_data(self.moddata)
    self.assertTrue(isinstance(json_string, str))

  def test_output_validity_without_load_error(self):
    json_string = rest.convert_module_data(self.moddata)
    values = json.loads(json_string)
    keys = ['tests', 'fullname', 'load_error', 'load_traceback']
    for key in keys:
      self.assertEqual(getattr(self.moddata, key), values[key])

  def test_output_validity_with_load_error(self):
    self.moddata.load_error = True
    self.moddata.load_traceback = 'some traceback string'
    json_string = rest.convert_module_data(self.moddata)
    values = json.loads(json_string)
    keys = ['tests', 'fullname', 'load_error', 'load_traceback']
    for key in keys:
      self.assertEqual(getattr(self.moddata, key), values[key])


class GetSubpackagesTest(unittest.TestCase):
  """Tests for the get_subpackages function."""

  def test_invalid_input(self):
    self.assertRaises(TypeError, rest.get_subpackages, None)
    self.assertRaises(TypeError, rest.get_subpackages, 5)
    self.assertRaises(TypeError, rest.get_subpackages, [''])

  def test_package_with_one_subpackage(self):
    subpackages = rest.get_subpackages(SAMPLE_PACKAGENAME)
    self.assertTrue(isinstance(subpackages, list))
    self.assertEqual(['subpackage'], subpackages)

  def test_package_with_no_subpackage(self):
    subpackages = rest.get_subpackages(SAMPLE_SUBPACKAGENAME)
    self.assertEqual([], subpackages)

  def test_module(self):
    subpackages = rest.get_subpackages(SAMPLE_MODULENAME)
    self.assertEqual([], subpackages)


class JsonizeModuleInformationTest(unittest.TestCase):
  """Tests for the jsonize_module_information function."""

  def setUp(self):
    self.moddata = models.ModuleData(fullname='package.module',
                                     tests=['testFoo', 'testBar'],
                                     load_error=False,
                                     load_traceback=None)

  # method, not a function is okay - pylint:disable-msg=R0201
  def get_expected_output(self, jsonized_moddata, jsonized_subpackages):
    return '{"subpackages": %s, "module_data": %s}' % (jsonized_subpackages,
                                                       jsonized_moddata)

  def test_invalid_input(self):
    self.assertRaises(TypeError, rest.jsonize_module_information, None, [])
    self.assertRaises(TypeError, rest.jsonize_module_information, 1, [])
    self.assertRaises(TypeError, rest.jsonize_module_information, '', [])
    self.assertRaises(TypeError, rest.jsonize_module_information,
                      self.moddata, [])
    self.assertRaises(TypeError, rest.jsonize_module_information, [], 1)
    self.assertRaises(TypeError, rest.jsonize_module_information, [], '')

  def test_empty_lists(self):
    jsonized_moddata = []
    jsonized_subpackages = []
    result = rest.jsonize_module_information(jsonized_moddata,
                                           jsonized_subpackages)
    expected = self.get_expected_output(jsonized_moddata, jsonized_subpackages)
    self.assertEqual(expected, result)

  def test_output_is_valid_json(self):
    jsonized_subpackages = []
    result = rest.jsonize_module_information([self.moddata],
                                           jsonized_subpackages)
    values = json.loads(result)
    self.assertEqual([], values['subpackages'])
    self.assertTrue('module_data' in values)
    moddata = values['module_data'][0]
    keys = ['tests', 'fullname', 'load_error', 'load_traceback']
    for key in keys:
      self.assertEqual(getattr(self.moddata, key), moddata[key])


class GetModuleDataTest(unittest.TestCase):
  """Tests for the get_module_data function."""

  def setUp(self):
    self.orig_getsubpackages = rest.get_subpackages
    self.expected_subpackages = ['foo', 'bar']
    rest.get_subpackages = lambda _: self.expected_subpackages
    self.conf = config.Config(test_package_names=['tests'],
                              test_module_pattern='^[\w]+_test$')
    self.orig_testnames = self.conf.test_package_names
    self.orig_getabspath = logic.get_abs_path_from_package_name


  def tearDown(self):
    rest.get_subpackages = self.orig_getsubpackages
    self.conf.test_package_names = self.orig_testnames
    logic.get_abs_path_from_package_name = self.orig_getabspath

  def test_invalid_input(self):
    self.assertRaises(TypeError, rest.get_module_data, None, self.conf)
    self.assertRaises(TypeError, rest.get_module_data, 5, self.conf)
    self.assertRaises(TypeError, rest.get_module_data, [''], self.conf)

  def test_empty_name(self):
    self.conf.test_package_names = self.expected_subpackages
    logic.get_abs_path_from_package_name = lambda _: self.expected_subpackages
    (subpackages, moduledata) = rest.get_module_data('', self.conf)
    self.assertEqual(self.expected_subpackages, subpackages)
    self.assertEqual([], moduledata)

  def test_existing_package(self):
    fullname = SAMPLE_PACKAGENAME
    (subpackages, moduledata) = rest.get_module_data(fullname, self.conf)
    self.assertEqual(self.expected_subpackages, subpackages)
    self.assertTrue(isinstance(moduledata, list))
    self.assertTrue(isinstance(moduledata[0], models.ModuleData))

  def test_non_existing_package(self):
    fullname = SAMPLE_PACKAGENAME + 'non_existing'
    self.assertRaises(rest.LoadError, rest.get_module_data, fullname,
                      self.conf)

  def test_existing_module(self):
    (subpackages, moduledata) = rest.get_module_data(SAMPLE_MODULENAME,
                                                     self.conf)
    self.assertEqual([], subpackages)
    self.assertTrue(isinstance(moduledata, list))
    self.assertTrue(isinstance(moduledata[0], models.ModuleData))

  def test_non_existing_module(self):
    self.assertRaises(rest.LoadError, rest.get_module_data,
                      SAMPLE_PACKAGENAME + '.non_exising', self.conf)

  def test_class(self):
    self.assertRaises(rest.IncorrectUsageError, rest.get_module_data,
                      SAMPLE_CLASSNAME, self.conf)

  def test_method(self):
    self.assertRaises(rest.IncorrectUsageError, rest.get_module_data,
                      SAMPLE_METHODNAME, self.conf)

  def test_load_error(self):
    fullname = '%s.brokenmodule_test' % SAMPLE_PACKAGENAME
    self.assertRaises(rest.LoadError, rest.get_module_data, fullname,
                      self.conf)


class GetTestResultDataTest(unittest.TestCase):
  """Tests for the get_test_result_data function."""

  def setUp(self):
    test_result = unittest.TestResult()
    result_name = 'package.module.testcase1'
    self.testresult = models.TestResultData(testresult=test_result,
                                            fullname=result_name)
    self.orig_runtest = logic.run_test
    logic.run_test = lambda _: self.testresult
    self.orig_loadmodules = logic.load_modules
    self.conf = config.Config(test_package_names=['foo', 'bar'],
                              test_module_pattern='^[\w]+_test$')

  def tearDown(self):
    logic.run_test = self.orig_runtest
    logic.load_modules = self.orig_loadmodules

  def test_invalid_input(self):
    self.assertRaises(TypeError, rest.get_test_result_data, None, self.conf)
    self.assertRaises(TypeError, rest.get_test_result_data, 5, self.conf)
    self.assertRaises(TypeError, rest.get_test_result_data, [''], self.conf)

  def test_empty_name(self):

    # okay to define instance variable - pylint:disable-msg=W0201
    self.testnames = []

    def register_test_names(name):
      self.testnames.append(name)
      return self.testresult

    logic.run_test = register_test_names
    logic.load_modules = lambda *args, **kwargs: 'foo'
    results = rest.get_test_result_data('', self.conf)
    self.assertTrue(len(self.testnames) > len(self.conf.test_package_names))
    self.assertTrue(results)
    for result in results:
      self.assertTrue(isinstance(result, models.TestResultData))

  def test_existing_package(self):
    results = rest.get_test_result_data(SAMPLE_PACKAGENAME, self.conf)
    self.assertTrue(results)
    for result in results:
      self.assertTrue(isinstance(result, models.TestResultData))

  def test_module(self):
    results = rest.get_test_result_data(SAMPLE_MODULENAME, self.conf)
    self.assertTrue(results)
    for result in results:
      self.assertTrue(isinstance(result, models.TestResultData))

  def test_class(self):
    results = rest.get_test_result_data(SAMPLE_CLASSNAME, self.conf)
    self.assertTrue(results)
    for result in results:
      self.assertTrue(isinstance(result, models.TestResultData))

  def test_method(self):
    results = rest.get_test_result_data(SAMPLE_METHODNAME, self.conf)
    self.assertTrue(results)
    for result in results:
      self.assertTrue(isinstance(result, models.TestResultData))

  def test_non_existing_test_object(self):
    self.assertRaises(rest.ObjectNotFoundError, rest.get_test_result_data,
                      'non-existing-name', self.conf)


class GetObjectTypeTest(unittest.TestCase):
  """Tests for the get_object_type function."""

  def test_invalid_input(self):
    self.assertRaises(TypeError, rest.get_object_type, 5)
    self.assertRaises(TypeError, rest.get_object_type, [''])

  def test_package(self):
    self.assertEqual('package', rest.get_object_type(SAMPLE_PACKAGENAME))

  def test_module(self):
    self.assertEqual('module', rest.get_object_type(SAMPLE_MODULENAME))

  def test_class(self):
    self.assertEqual('class', rest.get_object_type(SAMPLE_CLASSNAME))

  def test_method(self):
    self.assertEqual('method', rest.get_object_type(SAMPLE_METHODNAME))

  def test_empty_name(self):
    self.assertEqual('', rest.get_object_type(''))

  def test_non_existing_object(self):
    self.assertEqual('', rest.get_object_type('foo.bar.baz'))
