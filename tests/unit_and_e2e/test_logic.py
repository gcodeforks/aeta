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

"""Tests for the logic module of aeta."""



# Disable checking; pylint:disable-msg=C0111,C0103,W0212
# pylint:disable-msg=C0103,R0902,R0201,R0904
# - docstrings
# - access to protected members
# - too many public methods
# - setUp() and tearDown() method names
# - too many instance attributes
# - method could be a function

import copy
import inspect
import os
import sys
import types
import unittest

from aeta import config
from aeta import logic
from aeta import models
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


class GetAbsPathFromPackagenameTest(unittest.TestCase,
                                    utils.MockAttributeMixin):
  """Tests for the get_abs_path_from_package_name function."""

  # pylint:disable-msg=C0103
  def setUp(self):
    self.packagename = 'package.subpackage'
    self.abs_packagepath = os.path.join(_DEEP_ROOT_PATH, 'package',
                                        'subpackage')

  # pylint:disable-msg=C0103
  def tearDown(self):
    self.tear_down_attributes()

  def test_invalid_input(self):
    self.assertRaises(TypeError, logic.get_abs_path_from_package_name, None)

  def test_empty_package_name(self):
    self.assertEqual(None, logic.get_abs_path_from_package_name(''))

  def test_with_non_existing_package(self):

    @self.mock(logic)
    def load_module_from_module_name(name, errors, reload_mod,
                                     include_test_functions=True):
      return None
    self.assertEqual(None,
                     logic.get_abs_path_from_package_name(self.packagename))

  def test_with_existing_package(self):

    # pylint: disable-msg=W0613
    @self.mock(logic)
    def load_module_from_module_name(packagename, errors, reload_mod,
                                     include_test_functions=True):
      return types.ModuleType('foo')

    @self.mock(inspect)
    def getfile(module):
      return '%s/__init__.py' % _DEEP_ROOT_PATH

    self.assertEqual(_DEEP_ROOT_PATH + os.sep,
                     logic.get_abs_path_from_package_name(''))

  def test_init_module(self):
    """Ensure that the __init__ module is not considered a package."""

    @self.mock(logic)
    def load_module_from_module_name(packagename, errors, reload_mod,
                                     include_test_functions=True):
      return types.ModuleType('package.__init__')

    @self.mock(inspect)
    def getfile(module):
      return '%s/__init__.py' % _DEEP_ROOT_PATH

    self.assertEqual(None, logic.get_abs_path_from_package_name(''))


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
                      '', 5)
    self.assertRaises(TypeError, logic.load_module_from_module_name,
                      '', [], reload_mod=None)
    self.assertRaises(TypeError, logic.load_module_from_module_name,
                      '', [], include_import_error=None)
    self.assertRaises(TypeError, logic.load_module_from_module_name,
                      '', [], include_test_functions=None)

  def test_empty_module_name(self):
    self.assertEqual(None, logic.load_module_from_module_name('', []))

  def test_invalid_package(self):
    result_errors = []
    result_module = logic.load_module_from_module_name('--', result_errors)
    self.assertEqual(None, result_module)
    self.assertEqual([], result_errors)

  def test_include_import_error(self):
    result_errors = []
    result_module = logic.load_module_from_module_name(
        '--', result_errors, include_import_error=True)
    self.assertEqual(None, result_module)
    self.assertEqual(1, len(result_errors))
    self.assertEqual('--', result_errors[0][0])

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

  def test_test_functions(self):
    modulename = self.test_package_name + '.test_test_functions'
    result_errors = []
    # include_test_functions is True by default.
    result_module = logic.load_module_from_module_name(modulename,
                                                       result_errors)
    class_name = 'TestTestFunctionsWrappedTestFunctions'
    result_class = getattr(result_module, class_name, None)
    self.assertTrue(isinstance(result_class, type))
    self.assertTrue(issubclass(result_class, unittest.TestCase))

  def test_no_test_functions(self):
    modulename = self.test_package_name + '.test_test_functions'
    result_errors = []
    # The module might have been loaded by the previous test function, which
    # would have wrapped test functions.
    sys.modules.pop(modulename, None)
    result_module = logic.load_module_from_module_name(
        modulename, result_errors, include_test_functions=False)
    class_name = 'TestTestFunctionsWrappedTestFunctions'
    self.assertFalse(hasattr(result_module, class_name))


class GetModuleNamesInPackageTest(unittest.TestCase, utils.TestDataMixin):
  """Tests for the get_module_names_in_package function."""

  # pylint: disable-msg=C0103
  def setUp(self):
    self.setup_test_data()

  # pylint: disable-msg=C0103
  def tearDown(self):
    self.tear_down_test_data()

  def test_invalid_input(self):
    self.assertRaises(TypeError, logic.get_module_names_in_package, None, [])
    self.assertRaises(TypeError, logic.get_module_names_in_package, '', None)
    self.assertRaises(TypeError, logic.get_module_names_in_package, '', [],
                      module_pattern=None)
    self.assertRaises(TypeError, logic.get_module_names_in_package, '', [],
                      depth=None)

  def test_empty_package_name(self):
    result_modules = logic.get_module_names_in_package('', TEST_MODULE_PATTERN)
    self.assertEqual([], result_modules)

  def test_invalid_package_name(self):
    result_modules = logic.get_module_names_in_package('2',
                                                       TEST_MODULE_PATTERN)
    self.assertEqual([], result_modules)

  # acceptable name - pylint: disable-msg=C0103
  def test_valid_path_with_one_broken_module(self):
    result_modules = logic.get_module_names_in_package(self.test_package_name,
                                                       TEST_MODULE_PATTERN)
    self.assertEqual(9, len(result_modules))

  def test_depth_smaller_than_zero(self):
    self.assertRaises(ValueError, logic.get_module_names_in_package,
                      self.test_package_name, TEST_MODULE_PATTERN, depth=-1)

  def test_depth_limited(self):
    modules = logic.get_module_names_in_package(
        self.test_package_name, TEST_MODULE_PATTERN, depth=1)
    found_mod_from_subpackage = False
    for mod in modules:
      if 'subpackage' in mod:
        found_mod_from_subpackage = True
        break
    self.assertFalse(found_mod_from_subpackage)

  def test_depth_unlimited(self):
    modules = logic.get_module_names_in_package(
        self.test_package_name, TEST_MODULE_PATTERN, depth=0)
    found_mod_from_subpackage = False
    for mod in modules:
      if 'subpackage' in mod:
        found_mod_from_subpackage = True
        break
    self.assertTrue(found_mod_from_subpackage)


class IsPrefixTest(unittest.TestCase):
  """Tests for the _is_prefix function."""

  def test_is_prefix(self):
    self.assertTrue(logic._is_prefix('package.module',
                                     'package.module.Class.method'))
    self.assertTrue(logic._is_prefix('', 'something'))
    self.assertFalse(logic._is_prefix('a.b', 'a'))
    self.assertFalse(logic._is_prefix('a.b', 'a.c'))
    self.assertFalse(logic._is_prefix('package.module', 'package.module1'))
    self.assertFalse(logic._is_prefix('a', ''))


class IsInTestPackageTest(unittest.TestCase):
  """Tests for the _is_in_test_package function."""

  def test_is_in_test_package(self):
    conf = copy.copy(config.get_config())
    conf.test_package_names = ['a', 'b.c']
    self.assertTrue(logic._is_in_test_package('a', conf))
    self.assertTrue(logic._is_in_test_package('a.z', conf))
    self.assertTrue(logic._is_in_test_package('b.c', conf))
    self.assertTrue(logic._is_in_test_package('b.c.x', conf))
    self.assertFalse(logic._is_in_test_package('c', conf))
    self.assertFalse(logic._is_in_test_package('aaa', conf))
    self.assertFalse(logic._is_in_test_package('', conf))


class GetRequestedObjectTest(unittest.TestCase, utils.TestDataMixin):
  """Tests for the get_requested_object function."""

  def setUp(self):
    self.setup_test_data()
    self.config = copy.copy(config.get_config())
    self.config.test_package_names = [self.test_package_name]

  def tearDown(self):
    self.tear_down_test_data()

  def test_invalid_input(self):
    self.assertRaises(TypeError, logic.get_requested_object, None, self.config)

  def test_root(self):
    obj = logic.get_requested_object('', self.config)
    self.assertTrue(isinstance(obj, logic.Root))

  def test_invalid_name(self):
    fullname = self.test_package_name + '.a.non.existing.fullname'
    obj = logic.get_requested_object(fullname, self.config)
    self.assertTrue(isinstance(obj, logic.BadTest))
    self.assertFalse(obj.exists)
    self.assertEqual(1, len(obj.load_errors))
    fullname = self.test_package_name + '.no_elements_fullname'
    obj = logic.get_requested_object(fullname, self.config)
    self.assertTrue(isinstance(obj, logic.BadTest))
    self.assertFalse(obj.exists)
    self.assertEqual(1, len(obj.load_errors))

  def test_outside_test_package(self):
    self.config.test_package_names = [self.test_package_name + '.subpackage']
    fullname = self.test_package_name + '.test_goodmodule'
    obj = logic.get_requested_object(fullname, self.config)
    self.assertTrue(isinstance(obj, logic.BadTest))
    self.assertFalse(obj.exists)
    self.assertEqual(1, len(obj.load_errors))

  def test_package(self):
    result = logic.get_requested_object(self.test_package_name, self.config)
    self.assertTrue(isinstance(result, logic.Package))
    self.assertEqual(self.test_package_name, result.fullname)

  def test_module(self):
    fullname = self.test_package_name + '.test_goodmodule'
    result = logic.get_requested_object(fullname, self.config)
    self.assertTrue(isinstance(result, logic.Module))
    self.assertEqual(fullname, result.fullname)
    self.assertEqual(fullname, result.module.__name__)

  def test_class(self):
    fullname = self.test_package_name + '.test_goodmodule.Foo'
    result = logic.get_requested_object(fullname, self.config)
    self.assertTrue(isinstance(result, logic.Class))
    self.assertEqual(fullname, result.fullname)
    cls_name = '%s.%s' % (result.class_.__module__, result.class_.__name__)
    self.assertEqual(fullname, cls_name)

  def test_method(self):
    fullname = self.test_package_name + '.test_goodmodule.Foo.bar'
    result = logic.get_requested_object(fullname, self.config)
    self.assertTrue(isinstance(result, logic.Method))
    self.assertEqual(fullname, result.fullname)
    method_name = '%s.%s.%s' % (result.class_.__module__,
                                result.class_.__name__, result.method_name)
    self.assertEqual(fullname, method_name)

  def test_broken_module(self):
    fullname = self.test_package_name + '.test_brokenmodule'
    result = logic.get_requested_object(fullname, self.config)
    self.assertTrue(isinstance(result, logic.BadTest))
    self.assertEqual(1, len(result.load_errors))


class GetUnitsTest(unittest.TestCase, utils.TestDataMixin):
  """Tests for TestObject.get_units."""

  def setUp(self):
    self.setup_test_data()
    self.config = copy.copy(config.get_config())
    self.config.test_package_names = [self.test_package_name]
    self.config.test_module_pattern = '^test_[\w]+$'
    self.module_fixture = self.test_package_name + '.test_module_fixture'
    self.class_fixture = self.test_package_name + '.test_class_fixture'
    self.badnames = self.test_package_name + '.test_badnames'

  def tearDown(self):
    self.tear_down_test_data()

  def check(self, fullname, exp_names, exp_errs=None):
    """Checks that get_units returns what is expected.

    Args:
      fullname: The name to get test units in.
      exp_names: The expected test unit names, in any order.  The names are
          relative to fullname.
      exp_errs: The expected names of objects that failed to load, in any
          order.
    """
    errors_out = []
    units = (logic.get_requested_object(fullname, self.config)
             .get_units(self.config, errors_out))
    exp_fullnames = sorted([fullname + name for name in exp_names])
    self.assertEqual(exp_fullnames, sorted([u.fullname for u in units]))
    load_failed = [err[0] for err in errors_out]
    self.assertEqual(sorted(exp_errs or []), sorted(load_failed))


  def test_invalid_object(self):
    self.check('bad', [], ['bad'])

  def test_root(self):
    self.config.parallelize_modules = True
    self.config.parallelize_classes = True
    self.config.parallelize_methods = True
    subpackage = self.test_package_name + '.subpackage'
    self.config.test_package_names = [subpackage]
    self.check('', [subpackage + '.test_ham.FooTest.test_fail',
                    subpackage + '.test_ham.FooTest.test_pass'])

  def test_package(self):
    self.config.parallelize_modules = True
    self.config.parallelize_classes = True
    self.config.parallelize_methods = True
    subpackage = self.test_package_name + '.subpackage'
    self.check(subpackage, ['.test_ham.FooTest.test_fail',
                            '.test_ham.FooTest.test_pass'])

  def test_module_with_fixture(self):
    self.config.parallelize_modules = True
    self.config.parallelize_classes = True
    self.config.parallelize_methods = True
    self.check(self.module_fixture, [''])

  def test_module_without_fixture(self):
    self.config.parallelize_modules = True
    self.config.parallelize_classes = True
    self.config.parallelize_methods = True
    self.check(self.class_fixture,
               ['.HasClassFixture', '.HasNoClassFixture.test_fail',
                '.HasNoClassFixture.test_pass'])

  def test_no_parallel_classes(self):
    self.config.parallelize_modules = True
    self.config.parallelize_classes = False
    self.check(self.class_fixture, [''])

  def test_no_parallel_methods(self):
    self.config.parallelize_modules = True
    self.config.parallelize_classes = True
    self.config.parallelize_methods = False
    self.check(self.class_fixture, ['.HasClassFixture',
                                    '.HasNoClassFixture'])

  def test_class_with_fixture(self):
    self.config.parallelize_modules = True
    self.config.parallelize_classes = True
    self.config.parallelize_methods = True
    self.check(self.class_fixture + '.HasClassFixture', [''])

  def test_class_without_fixture(self):
    self.config.parallelize_modules = True
    self.config.parallelize_classes = True
    self.config.parallelize_methods = True
    self.check(self.class_fixture + '.HasNoClassFixture',
               ['.test_fail', '.test_pass'])

  def test_load_error(self):
    self.config.parallelize_modules = True
    self.config.parallelize_classes = True
    self.config.parallelize_methods = True
    broken_module = self.test_package_name + '.test_brokenmodule'
    self.check(broken_module, [], [broken_module])

  def test_module_bad_name(self):
    self.config.parallelize_modules = True
    self.config.parallelize_classes = False
    # The module should be found despite its __name__ not matching
    # test_module_pattern.
    units = (logic.get_requested_object(self.test_package_name, self.config)
             .get_units(self.config))
    self.assertTrue(self.badnames in [unit.fullname for unit in units])

  def test_class_bad_names(self):
    self.config.parallelize_modules = True
    self.config.parallelize_classes = True
    self.check(self.badnames,
               ['.ClassWithDifferentMethodNames', '.ClassWithDifferentModule',
                '.ClassWithDifferentName1', '.ClassWithDifferentName2'])

  def test_method_bad_names(self):
    self.config.parallelize_modules = True
    self.config.parallelize_classes = True
    self.config.parallelize_methods = True
    class_name = self.badnames + '.ClassWithDifferentMethodNames'
    self.check(class_name, ['.test_method1', '.test_method2'])


def check_names_and_errors(self, fullname, exp_names, fullnames, exp_errs,
                           errs):
  exp_fullnames = [fullname + name for name in exp_names]
  self.assertEqual(sorted(exp_fullnames), sorted(fullnames))
  load_failed = [err[0] for err in errors_out]
  self.assertEqual(sorted(exp_errs or []), sorted(load_failed))


class GetMethodsTest(unittest.TestCase, utils.TestDataMixin):
  """Tests for the TestObject.get_methods method."""

  def setUp(self):
    self.setup_test_data()
    self.config = copy.copy(config.get_config())
    self.config.test_package_names = [self.test_package_name]
    self.config.test_module_pattern = '^test_[\w]+$'
    self.class_fixture = self.test_package_name + '.test_class_fixture'
    self.class_with_fixture = self.class_fixture + '.HasClassFixture'
    self.class_without_fixture = self.class_fixture + '.HasNoClassFixture'

  def tearDown(self):
    self.tear_down_test_data()

  def check(self, fullname, exp_names, exp_errs=None):
    """Checks that get_methods returns what is expected.

    Args:
      fullname: The name to get test methods in.
      exp_names: The expected test method names, in any order.  The names are
          relative to fullname.
      exp_errs: The expected names of objects that failed to load, in any
          order.
    """
    errors_out = []
    methods = (logic.get_requested_object(fullname, self.config)
               .get_methods(self.config, errors_out))
    fullnames = [method.fullname for method in methods]
    exp_fullnames = [fullname + name for name in exp_names]
    self.assertEqual(sorted(exp_fullnames), sorted(fullnames))
    load_failed = [err[0] for err in errors_out]
    self.assertEqual(sorted(exp_errs or []), sorted(load_failed))

  def test_invalid_name(self):
    self.check('bad', [], ['bad'])

  def test_root(self):
    subpackage = self.test_package_name + '.subpackage'
    self.config.test_package_names = [subpackage]
    prefix = subpackage + '.test_ham.FooTest'
    self.check('', [prefix + '.test_pass', prefix + '.test_fail'])

  def test_root_module(self):
    module = self.test_package_name + '.test_one_testcase'
    self.config.test_package_names = [module]
    self.check('', [module + '.SimpleTestCase.test_pass',
                    module + '.SimpleTestCase.test_fail'])

  def test_root_bad_module(self):
    module = self.test_package_name + '.test_badmodule'
    self.config.test_package_names = [module]
    self.check('', [], [module])

  def test_package(self):
    subpackage = self.test_package_name + '.subpackage'
    self.check(subpackage, ['.test_ham.FooTest.test_pass',
                            '.test_ham.FooTest.test_fail'])

  def test_module(self):
    self.check(self.class_fixture,
               ['.HasClassFixture.test_has_class_value',
                '.HasClassFixture.test_has_bad_class_value',
                '.HasNoClassFixture.test_pass',
                '.HasNoClassFixture.test_fail'])

  def test_class(self):
    self.check(self.class_with_fixture,
               ['.test_has_class_value', '.test_has_bad_class_value'])

  def test_method(self):
    method = self.class_with_fixture + '.test_has_class_value'
    self.check(method, [''])

  def test_bad_names(self):
    badnames = self.test_package_name + '.test_badnames'
    self.check(badnames, ['.ClassWithDifferentModule.test_method',
                          '.ClassWithDifferentName1.test_method',
                          '.ClassWithDifferentName2.test_method',
                          '.ClassWithDifferentMethodNames.test_method1',
                          '.ClassWithDifferentMethodNames.test_method2'])


class GetTestSuiteTest(unittest.TestCase, utils.TestDataMixin):
  """Tests for TestObject.get_test_suite."""

  def setUp(self):
    self.setup_test_data()
    self.config = copy.copy(config.get_config())
    self.config.test_package_names = [self.test_package_name]
    self.config.test_module_pattern = '^test_[\w]+$'
    self.class_fixture = self.test_package_name + '.test_class_fixture'
    self.class_with_fixture = self.class_fixture + '.HasClassFixture'
    self.class_without_fixture = self.class_fixture + '.HasNoClassFixture'

  def tearDown(self):
    self.tear_down_test_data()

  def check(self, fullname, exp_names, exp_errs=None):
    """Checks that get_suite returns what is expected.

    Args:
      fullname: The name to get a test suite from.
      exp_names: The expected test method names, in any order.  The names are
          relative to fullname.
      exp_errs: The expected names of objects that failed to load, in any
          order.
    """
    errors_out = []
    suite = (logic.get_requested_object(fullname, self.config)
             .get_suite(self.config, errors_out))
    self.assertTrue(isinstance(suite, unittest.TestSuite))
    fullnames = [test.fullname for test in suite]
    exp_fullnames = [fullname + name for name in exp_names]
    self.assertEqual(sorted(exp_fullnames), sorted(fullnames))
    load_failed = [err[0] for err in errors_out]
    self.assertEqual(sorted(exp_errs or []), sorted(load_failed))

  def test_invalid_name(self):
    self.check('bad', [], ['bad'])

  def test_package(self):
    subpackage = self.test_package_name + '.subpackage'
    self.check(subpackage, ['.test_ham.FooTest.test_pass',
                            '.test_ham.FooTest.test_fail'])

  def test_bad_names(self):
    badnames = self.test_package_name + '.test_badnames'
    self.check(badnames, ['.ClassWithDifferentModule.test_method',
                          '.ClassWithDifferentName1.test_method',
                          '.ClassWithDifferentName2.test_method',
                          '.ClassWithDifferentMethodNames.test_method1',
                          '.ClassWithDifferentMethodNames.test_method2'])
