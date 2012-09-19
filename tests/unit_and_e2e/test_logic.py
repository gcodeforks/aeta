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

"""Tests for the logic module of aeta."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

# Disable checking; pylint:disable-msg=C0111,C0103,W0212
# pylint:disable-msg=C0103,R0902,R0201,R0904
# - docstrings
# - access to protected members
# - too many public methods
# - setUp() and tearDown() method names
# - too many instance attributes
# - method could be a function

import inspect
import os
import sys
import types
import unittest

from aeta import logic
from tests import utils

_REL_PATH = 'a/relative/path'

_NATIVE_REL_PATH = os.sep.join(_REL_PATH.split('/'))

_DEEP_ROOT_PATH = os.sep.join(['a', 'deep', 'root', 'path'])

if sys.platform.startswith('win'):
  _DEEP_ROOT_PATH = os.path.join('C:', _DEEP_ROOT_PATH)
else:
  _DEEP_ROOT_PATH = os.sep + _DEEP_ROOT_PATH

# Pattern of test modules.
TEST_MODULE_PATTERN = r'^test_[\w]+$'

class GetAbsPathFromPackagenameTest(unittest.TestCase):
  """Tests for the get_abs_path_from_package_name function."""

  # pylint:disable-msg=C0103
  def setUp(self):
    self.packagename = 'package.subpackage'
    self.abs_packagepath = os.path.join(_DEEP_ROOT_PATH, 'package',
                                        'subpackage')
    self.orig_isdir = os.path.isdir
    self.orig_isfile = os.path.isfile
    self.original_path_exists = os.path.exists
    # name okay - pylint: disable-msg=C0103
    self.orig_load_module_from_module_name = logic.load_module_from_module_name
    self.orig_inspect_getfile = inspect.getfile

  # pylint:disable-msg=C0103
  def tearDown(self):
    os.path.isfile = self.orig_isfile
    os.path.isdir = self.orig_isdir
    os.path.exists = self.original_path_exists

    logic.load_module_from_module_name = self.orig_load_module_from_module_name
    inspect.getfile = self.orig_inspect_getfile

  def test_invalid_input(self):
    self.assertRaises(TypeError, logic.get_abs_path_from_package_name, None)

  def test_empty_package_name(self):
    self.assertEqual(None, logic.get_abs_path_from_package_name(''))

  def test_with_non_existing_package(self):
    logic.load_module_from_module_name = lambda name, errors, reload_mod: None
    self.assertEqual(None,
                     logic.get_abs_path_from_package_name(self.packagename))

  def test_with_existing_package(self):

    # pylint: disable-msg=W0613
    def mock_load_module(packagename, errors, reload_mod):
      return types.ModuleType('foo')
    logic.load_module_from_module_name = mock_load_module
    inspect.getfile = lambda _: '%s/__init__.py' % _DEEP_ROOT_PATH

    self.assertEqual(_DEEP_ROOT_PATH + os.sep,
                     logic.get_abs_path_from_package_name(''))


class GetRootRelativePathTest(unittest.TestCase):
  """Tests for the get_root_relative_path function."""

  # pylint: disable-msg=C0103
  def setUp(self):
    self.orig_isdir = os.path.isdir

  # pylint: disable-msg=C0103
  def tearDown(self):
    os.path.isdir = self.orig_isdir

  def test_invalid_input(self):
    self.assertRaises(TypeError, logic.get_root_relative_path, None, '')
    self.assertRaises(TypeError, logic.get_root_relative_path, '', None)

  def test_no_root(self):
    self.assertEqual(None, logic.get_root_relative_path('', ''))
    self.assertEqual(None, logic.get_root_relative_path('/', ''))

  def test_with_root(self):
    os.path.isdir = lambda x: True
    if sys.platform.startswith('win'):
      self.assertEqual(None, logic.get_root_relative_path('/', 'C:/'))
      self.assertEqual('', logic.get_root_relative_path('C:/', 'C:/'))
    else:
      self.assertEqual('', logic.get_root_relative_path('/', '/'))

  def test_invalid_relative_path(self):
    os.path.isdir = lambda x: True
    self.assertEqual(None,
                     logic.get_root_relative_path('',
                                               '/a/deep/rootdirectory'))
    self.assertEqual(None, logic.get_root_relative_path('/',
                                                     '/a/deep/rootdirectory'))
    self.assertEqual(None, logic.get_root_relative_path('/',
                                                     '/a/deep/rootdirectory/'))
    self.assertEqual(None, logic.get_root_relative_path('some/other/path',
                                                     '/a/deep/rootdirectory'))
    self.assertEqual('', logic.get_root_relative_path(_DEEP_ROOT_PATH,
                                                   _DEEP_ROOT_PATH))

  def test_valid_relative_path(self):
    os.path.isdir = lambda x: True
    self.assertEqual(_REL_PATH, logic.get_root_relative_path(
        _DEEP_ROOT_PATH + os.sep + _REL_PATH,
        _DEEP_ROOT_PATH))

  # acceptable name - pylint: disable-msg=C0103
  def test_relative_path_partly_included_in_root(self):
    os.path.isdir = lambda x: True
    path = '/home/foobar/hello'
    root = '/home/foo'
    self.assertEqual(None, logic.get_root_relative_path(path, root))


class is_moduleTest(unittest.TestCase):
  """Tests for the is_module function."""

  def test_invalid_nput(self):
    self.assertRaises(TypeError, logic.is_module, None)

  def test_empty_input(self):
    self.assertEqual(False, logic.is_module(''))

  def test_invalid_module(self):
    self.assertEqual(False, logic.is_module('1'))
    self.assertEqual(False, logic.is_module('--'))

  def test_valid_module(self):
    self.assertEqual(True, logic.is_module(self.__module__))


class LoadModuleFromModuleNameTest(unittest.TestCase, utils.TestDataMixin):
  """Tests for the load_module_from_module_name function."""

  def setUp(self):
    self.setup_test_data()

  def tearDown(self):
    self.tear_down_test_data()

  def test_invalid_input(self):
    self.assertRaises(TypeError, logic.load_module_from_module_name,
                      None, [])
    self.assertRaises(TypeError, logic.load_module_from_module_name,
                      '', None)
    self.assertRaises(TypeError, logic.load_module_from_module_name,
                      '', [], reload_mod=None)

  def test_empty_module_nname(self):
    self.assertEqual(None, logic.load_module_from_module_name('', []))

  def test_invalid_package(self):
    result_errors = []
    result_module = logic.load_module_from_module_name('--',
                                                   result_errors)
    self.assertEqual(None, result_module)
    self.assertEqual(1, len(result_errors))

  def test_valid_package(self):
    result_errors = []
    result_module = logic.load_module_from_module_name(self.test_package_name,
                                                       result_errors)
    self.assertNotEqual(None, result_module)
    self.assertEqual([], result_errors)

  def test_broken_module(self):
    modulename = self.test_package_name + '.test_brokenmodule'
    result_errors = []
    result_module = logic.load_module_from_module_name(modulename,
                                                   result_errors)
    self.assertEqual(None, result_module)
    self.assertEqual(1, len(result_errors))

  def test_valid_module(self):
    modulename = self.test_package_name + '.test_goodmodule'
    result_errors = []
    result_module = logic.load_module_from_module_name(modulename,
                                                   result_errors)
    self.assertNotEqual(None, result_module)
    self.assertEqual([], result_errors)


class LoadModulesTest(unittest.TestCase, utils.TestDataMixin):
  """Tests for the load_modules function."""

  # pylint: disable-msg=C0103
  def setUp(self):
    self.setup_test_data()

  # pylint: disable-msg=C0103
  def tearDown(self):
    self.tear_down_test_data()

  def test_invalid_input(self):
    self.assertRaises(TypeError, logic.load_modules, None, [])
    self.assertRaises(TypeError, logic.load_modules, '', None)
    self.assertRaises(TypeError, logic.load_modules, '', [],
                      module_pattern=None)
    self.assertRaises(TypeError, logic.load_modules, '', [], depth=None)

  def test_empty_package_name(self):
    result_errors = []
    result_modules = logic.load_modules('', result_errors, TEST_MODULE_PATTERN)
    self.assertEqual([], result_modules)
    self.assertEqual([], result_errors)

  def test_invalid_package_name(self):
    result_errors = []
    result_modules = logic.load_modules('2', result_errors,
                                        TEST_MODULE_PATTERN)
    self.assertEqual([], result_modules)
    self.assertEqual([], result_errors)

  # acceptable name - pylint: disable-msg=C0103
  def test_valid_path_with_one_broken_module(self):
    result_errors = []
    result_modules = logic.load_modules(self.test_package_name,
                                        result_errors,
                                        TEST_MODULE_PATTERN)
    self.assertEqual(4, len(result_modules))
    self.assertEqual(1, len(result_errors))

  def test_depth_smaller_than_zero(self):
    self.assertRaises(ValueError, logic.load_modules, self.test_package_name,
                      [], TEST_MODULE_PATTERN, depth=-1)

  def test_depth_limited(self):
    modules = logic.load_modules(self.test_package_name, [],
                                 TEST_MODULE_PATTERN, depth=1)
    found_mod_from_subpackage = False
    for mod in modules:
      if 'subpackage' in mod.__name__:
        found_mod_from_subpackage = True
        break
    self.assertFalse(found_mod_from_subpackage)

  def test_depth_unlimited(self):
    modules = logic.load_modules(self.test_package_name, [],
                                 TEST_MODULE_PATTERN, depth=0)
    found_mod_from_subpackage = False
    for mod in modules:
      if 'subpackage' in mod.__name__:
        found_mod_from_subpackage = True
        break
    self.assertTrue(found_mod_from_subpackage)


class GetRequestedObjectTest(unittest.TestCase, utils.TestDataMixin):
  """Tests for the get_requested_object function."""

  def setUp(self):
    self.setup_test_data()

  def tearDown(self):
    self.tear_down_test_data()

  def test_invalid_input(self):
    self.assertRaises(TypeError, logic.get_requested_object, None)

  def test_empty_name(self):
    self.assertEqual(None, logic.get_requested_object(''))

  def test_invalid_name(self):
    self.assertEqual(None,
                     logic.get_requested_object('a.non.existing.fullname'))
    self.assertEqual(None, logic.get_requested_object('no_elements_fullname'))

  def test_package(self):
    result = logic.get_requested_object(self.test_package_name)
    self.assertNotEqual(None, result)
    self.assertTrue(isinstance(result, types.ModuleType))
    self.assertEqual(self.test_package_name, result.__name__)

  def test_module(self):
    fullname = self.test_package_name + '.test_goodmodule'
    result = logic.get_requested_object(fullname)
    self.assertNotEqual(None, result)
    self.assertTrue(isinstance(result, types.ModuleType))
    self.assertEqual(fullname, result.__name__)

  def test_class(self):
    fullname = self.test_package_name + '.test_goodmodule.Foo'
    result = logic.get_requested_object(fullname)
    self.assertNotEqual(None, result)
    self.assertTrue(isinstance(result, type))
    self.assertEqual(fullname, result.__module__ + '.' + result.__name__)

  def test_method(self):
    fullname = self.test_package_name + '.test_goodmodule.Foo.bar'
    result = logic.get_requested_object(fullname)
    self.assertNotEqual(None, result)
    self.assertTrue(isinstance(result, types.MethodType))
    result_name = result.__module__ + '.' + result.im_class.__name__
    result_name += '.' + result.__name__
    self.assertEqual(fullname, result_name)


class ExtractTestcasesAndTestMethodNamesTest(unittest.TestCase):
  """Tests for the extract_test_cases_and_method_names function."""

  def test_invalid_input(self):
    self.assertRaises(TypeError, logic.extract_test_cases_and_method_names,
                      None)

  def test_empty_module(self):
    module = types.ModuleType('foo')
    self.assertEqual({}, logic.extract_test_cases_and_method_names(module))

  def test_complex_module(self):
    # use this very module
    module = inspect.getmodule(self)
    result = logic.extract_test_cases_and_method_names(module)
    self.assertNotEqual({}, result)
    members = inspect.getmembers(module)
    for _, value in members:
      if isinstance(value, type) and issubclass(value, unittest.TestCase):
        class_name = value.__name__
        # each unittest defined in this module should be found
        self.assertTrue(class_name in result.keys())
        # each unittest should define at least one test method
        self.assertNotEqual(0, len(result[class_name]))
        # this particular method should be found as well
        if class_name == type(self).__name__:
          this_function = inspect.getframeinfo(inspect.currentframe())[2]
          self.assertTrue(this_function in result[class_name])


class CreateModuleDataTest(unittest.TestCase):
  """Tests for the create_module_data function."""

  def test_empty_modules_and_errors(self):
    self.assertEqual([], logic.create_module_data([], []))

  def test_invalid_input(self):
    self.assertRaises(TypeError, logic.create_module_data, None, None)
    self.assertRaises(TypeError, logic.create_module_data, None, [])
    self.assertRaises(TypeError, logic.create_module_data, [], None)

  def test_empty_module(self):
    module = types.ModuleType('foo')
    modules = [module]
    errors = []
    result = logic.create_module_data(modules, errors)
    self.assertEqual(1, len(result))
    moduledata = result[0]
    self.assertEqual(module.__name__, moduledata.fullname)
    self.assertEqual({}, moduledata.tests)
    self.assertEqual(False, moduledata.load_error)
    self.assertEqual(None, moduledata.load_traceback)

  def test_module_with_test_case(self):
    module = types.ModuleType('foo')
    class_ = type(self)
    class_name = class_.__name__
    setattr(module, class_name, class_)
    modules = [module]
    errors = []
    result = logic.create_module_data(modules, errors)
    self.assertEqual(1, len(result))
    moduledata = result[0]
    self.assertEqual(module.__name__, moduledata.fullname)
    testmethod_names = []
    for  attr in dir(class_):
      if attr.startswith('test'):
        testmethod_names.append(attr)
    self.assertEqual(1, len(moduledata.tests))
    extracted_testmethods = moduledata.tests.values()[0]
    self.assertEqual(testmethod_names, extracted_testmethods)
    self.assertEqual(False, moduledata.load_error)
    self.assertEqual(None, moduledata.load_traceback)

  def test_no_module_two_errors(self):
    modules = []
    error1 = ('package.subpackage.module_foo', 'some string')
    error2 = ('package.subpackage.module_bar', 'some other string')
    errors = [error1, error2]
    result = logic.create_module_data(modules, errors)
    self.assertEqual(2, len(result))
    for index in range(len(result)):
      self.assertEqual(errors[index][0], result[index].fullname)
      self.assertEqual({}, result[index].tests)
      self.assertEqual(True, result[index].load_error)
      self.assertEqual(errors[index][1], result[index].load_traceback)


class RunTestAndCaptureOutputTest(unittest.TestCase):
  """Tests for _run_test_and_capture_output."""

  def setUp(self):
    self.orig_stdout = logic.sys.stdout
    self.orig_stderr = logic.sys.stderr

  def tearDown(self):
    logic.sys.stdout = self.orig_stdout
    logic.sys.stderr = self.orig_stderr

  def test_invalid_input(self):
    for invalid in [None, 0, []]:
      self.assertRaises(TypeError, logic.create_module_data, invalid)

  def test_test_result(self):

    class Test(unittest.TestCase):

      def test_foo(self):
        self.assertTrue(True)

      def test_bar(self):
        self.assertTrue(False)

      def test_baz(self):
        raise ValueError

    suite = unittest.makeSuite(Test)
    testresult, _ = logic._run_test_and_capture_output(suite)
    self.assertEqual(3, testresult.testsRun)
    self.assertEqual(1, len(testresult.failures))
    self.assertEqual(1, len(testresult.errors))

  def test_restored_redirects(self):

    class Test(unittest.TestCase):

      def test_foo(self):
        raise ValueError

    suite = unittest.makeSuite(Test)
    logic._run_test_and_capture_output(suite)
    self.assertEqual(self.orig_stdout, logic.sys.stdout)
    self.assertEqual(self.orig_stderr, logic.sys.stderr)

  def test_stdout_redirect(self):
    expected_output = 'hello world'

    class Test(unittest.TestCase):

      def test_foo(self):
        print expected_output

    suite = unittest.makeSuite(Test)
    _, output = logic._run_test_and_capture_output(suite)
    self.assertTrue(output.find(expected_output) > 0)

  def test_stderr_redirect(self):
    expected_output = 'hello world'

    class Test(unittest.TestCase):

      def test_foo(self):
        print >> sys.stderr, expected_output

    suite = unittest.makeSuite(Test)
    _, output = logic._run_test_and_capture_output(suite)
    self.assertTrue(output.find(expected_output) > 0)


class RunTestTest(unittest.TestCase):
  """Tests for the run_test function."""

  def setUp(self):

    class SimpleTestCase(unittest.TestCase):

      def test_pass(self):
        self.assertTrue(True)

      def test_fail(self):
        self.fail()

    self.testcase = SimpleTestCase

  def test_no_test_object(self):
    self.assertRaises(TypeError, logic.run_test, None)
    self.assertRaises(TypeError, logic.run_test, [])

  def test_test_module_with_no_test_cases(self):
    module = types.ModuleType('foo')
    result = logic.run_test(module)
    self.assertEqual(module.__name__, result.fullname)
    self.assertEqual([], result.errors)
    self.assertEqual([], result.failures)
    self.assertEqual(0, result.testsRun)
    self.assertEqual(True, result.passed)
    self.assertTrue(len(result.output) > 1)

  def test_test_module_with_one_test_case(self):
    module = types.ModuleType('foo')
    setattr(module, 'SimpleTestCase', self.testcase)
    result = logic.run_test(module)
    self.assertEqual(module.__name__, result.fullname)
    self.assertEqual([], result.errors)
    self.assertEqual(1, len(result.failures))
    self.assertEqual(2, result.testsRun)
    self.assertEqual(False, result.passed)
    self.assertTrue(len(result.output) > 1)

  def test_test_case(self):
    result = logic.run_test(self.testcase)
    fullname = self.__module__ + '.' + self.testcase.__name__
    self.assertEqual(fullname, result.fullname)
    self.assertEqual([], result.errors)
    self.assertEqual(1, len(result.failures))
    self.assertEqual(2, result.testsRun)
    self.assertEqual(False, result.passed)
    self.assertTrue(len(result.output) > 1)

  def test_test_method_pass(self):
    result = logic.run_test(self.testcase.test_pass)
    fullname = self.__module__ + '.' + self.testcase.__name__ + '.'
    fullname += self.testcase.test_pass.__name__
    self.assertEqual(fullname, result.fullname)
    self.assertEqual([], result.errors)
    self.assertEqual([], result.failures)
    self.assertEqual(1, result.testsRun)
    self.assertEqual(True, result.passed)
    self.assertTrue(len(result.output) > 1)

  def test_test_method_fail(self):
    result = logic.run_test(self.testcase.test_fail)
    fullname = self.__module__ + '.' + self.testcase.__name__ + '.'
    fullname += self.testcase.test_fail.__name__
    self.assertEqual(fullname, result.fullname)
    self.assertEqual([], result.errors)
    self.assertEqual(1, len(result.failures))
    self.assertEqual(1, result.testsRun)
    self.assertEqual(False, result.passed)
    self.assertTrue(len(result.output) > 1)


class LoadAndRunTestsTest(unittest.TestCase, utils.TestDataMixin):
  """Tests for the load_and_run_tests function."""

  # pylint:disable-msg=C0103
  def setUp(self):
    self.setup_test_data()
    self.module_name = self.test_package_name + '.test_one_testcase'
    self.test_class_name = self.module_name + '.SimpleTestCase'
    self.test_method_name = self.test_class_name + '.test_pass'

  # pylint:disable-msg=C0103
  def tearDown(self):
    self.tear_down_test_data()

  def test_invalid_input(self):
    self.assertRaises(TypeError, logic.load_and_run_tests, None, '')
    self.assertRaises(TypeError, logic.load_and_run_tests, [], '')

  def test_empty_name(self):
    self.assertEqual([], logic.load_and_run_tests('', TEST_MODULE_PATTERN))

  # TODO(schuppe): remove or fix this method or fix behavior.
  # def test_test_module_with_no_test_cases(self):
  #   fullname = self.test_package_name + '.no_testcase_test'
  #   results = logic.load_and_run_tests(fullname)
  #   self.assertEqual([], results, results[0].output)

  # acceptable name - pylint:disable-msg=C0103
  def test_test_module_with_one_test_case(self):
    fullname = self.module_name
    results = logic.load_and_run_tests(fullname, TEST_MODULE_PATTERN)
    self.assertEqual(1, len(results))
    data = results[0]
    self.assertEqual(fullname, data.fullname)
    self.assertEqual([], data.errors)
    self.assertEqual(1, len(data.failures))
    self.assertEqual(2, data.testsRun)
    self.assertTrue(data.output)
    self.assertEqual(False, data.passed)

  def test_test_case(self):
    fullname = self.test_class_name
    results = logic.load_and_run_tests(fullname, TEST_MODULE_PATTERN)
    self.assertEqual(1, len(results))
    data = results[0]
    self.assertEqual(fullname, data.fullname)
    self.assertEqual([], data.errors)
    self.assertEqual(1, len(data.failures))
    self.assertEqual(2, data.testsRun)
    self.assertTrue(data.output)
    self.assertEqual(False, data.passed)

  def test_test_method(self):
    fullname = self.test_method_name
    results = logic.load_and_run_tests(fullname, TEST_MODULE_PATTERN)
    self.assertEqual(1, len(results))
    data = results[0]
    self.assertEqual(fullname, data.fullname)
    self.assertEqual([], data.errors)
    self.assertEqual([], data.failures)
    self.assertEqual(1, data.testsRun)
    self.assertTrue(data.output)
    self.assertEqual(True, data.passed)
