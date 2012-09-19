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

# Disable checking; pylint: disable-msg=C0111,W0212,R0904,C0103,R0902,R0201
# - docstrings
# - access to protected members
# - too many public methods
# - setUp() and tearDown() method names
# - too many instance attributes
# - method could be a function

import StringIO
import sys
import types
import unittest
import urllib2

import simplejson as json

from aeta import local_client


def get_mock_get_url_content(return_value, error_code=None,
                           error_message=None):
  """Create a mock _get_url_content function.

  Args:
    return_value: Content the mocked function should return.
    error_code: urllib2.HTTPError the function should raise.
    error_message: Optional error message to be returned.

  Returns:
    A mock function for local_client._get_url_content.
  """

  if not error_message:
    error_message = 'an error message'

  def mock_get_url_content(url):
    if not error_code:
      return return_value
    error = urllib2.HTTPError(url, error_code, '', None, None)
    error.read = lambda: error_message
    raise error

  return mock_get_url_content


def build_module_data_str(fullname, tests=None, load_error=False,
                          load_traceback=None):
  """Build a module_data object as returned by the REST interface.

  Args:
    fullname: full name of a package of module.
    tests: A dictionary with test classes as key values, and a list of
           test method names.
    load_error: Dalse if the object could be loaded, true if an error
             occured.
    load_traceback: Rhe traceback of the load error or None.

  Returns:
    A jsonized module_data object as returned by the REST interface.
  """
  module_data = {'fullname': fullname}
  if tests:
    module_data['tests'] = tests
  module_data['load_error'] = load_error
  module_data['load_traceback'] = load_traceback
  return json.dumps(module_data)


def build_test_data_response(module_data_strings, subpackages):
  """Build a JSON string as returned by the aeta REST interface.

  Args:
    module_data_strings: List of module_data strings.
    subpackages: List of subpackages.

  Returns:
    A valid JSON string.
  """
  json_string = '{"module_data": [%s], ' % ','.join(module_data_strings)
  json_string += '"subpackages": %s}' % subpackages
  json_string = json_string.replace("'", '"')
  return json_string


class TestModuleDataTest(unittest.TestCase):
  """Tests for _TestModuleData."""

  def setUp(self):
    self.valid_dict = {'fullname': 'package.module.class.method',
                       'load_traceback': 'multi-line\nstring',
                       'tests': {'class': 'method1', 'method2': 'method3'}
                      }

  def test_load_from_dict_empty_dict(self):
    d = {}
    mod_data = local_client._TestModuleData.load_from_dict(d)
    self.assertEqual(None, mod_data.fullname)
    self.assertEqual(None, mod_data.load_traceback)
    self.assertEqual({}, mod_data.tests)

  def test_load_from_valid_dict(self):
    d = self.valid_dict
    mod_data = local_client._TestModuleData.load_from_dict(d)
    self.assertEqual(d['fullname'], mod_data.fullname)
    self.assertEqual(d['load_traceback'], mod_data.load_traceback)
    self.assertEqual(d['tests'], mod_data.tests)

  def test_load_from_valid_dict_with_extra_entries(self):
    d = self.valid_dict
    d['foo'] = 1
    d['bar'] = 2
    mod_data = local_client._TestModuleData.load_from_dict(d)
    self.assertEqual(d['fullname'], mod_data.fullname)
    self.assertEqual(d['load_traceback'], mod_data.load_traceback)
    self.assertEqual(d['tests'], mod_data.tests)

  def test_load_from_valid_dict_with_unicode_values(self):
    d = self.valid_dict
    for key in ['fullname', 'load_traceback', 'tests']:
      value = d[key]
      del d[key]
      d[unicode(key)] = value
    mod_data = local_client._TestModuleData.load_from_dict(d)
    self.assertEqual(d['fullname'], mod_data.fullname)
    self.assertEqual(d['load_traceback'], mod_data.load_traceback)
    self.assertEqual(d['tests'], mod_data.tests)


class CreateModuleTest(unittest.TestCase):
  """Tests for _create_module."""

  def test_default(self):
    mod = local_client._create_module('foo')
    self.assertEqual(types.ModuleType, type(mod))

  def test_invalid_parent(self):
    invalids = [1, 's', [], {}]
    for invalid in invalids:
      self.assertRaises(TypeError, local_client._create_module, 'foo', invalid)

  def test_unicode_name(self):
    mod = local_client._create_module(u'foo')
    self.assertEqual('foo', mod.__name__)

  def test_module_assigned_to_parent(self):
    parent_mod = types.ModuleType('parent')
    mod = local_client._create_module('foo', parent_mod)
    self.assertTrue(hasattr(parent_mod, 'foo'))
    self.assertEqual(parent_mod.foo, mod)

  def test_attribute_already_exists(self):
    parent_mod = types.ModuleType('parent')
    parent_mod.foo = 42
    self.assertRaises(ValueError, local_client._create_module, 'foo',
                      parent_mod)


class CreateClassTest(unittest.TestCase):
  """Tests for _create_class."""

  def setUp(self):
    self.base_class = unittest.TestCase
    self.parent_mod = types.ModuleType('parent')

  def test_default(self):
    cls = local_client._create_class('foo', self.base_class, self.parent_mod)
    self.assertEqual(type, type(cls))
    self.assertTrue(issubclass(cls, self.base_class))
    self.assertTrue(hasattr(self.parent_mod, 'foo'))
    self.assertEqual(self.parent_mod.foo, cls)

  def test_invalid_base_class(self):
    invalids = [1, 's', [], {}]
    for invalid in invalids:
      self.assertRaises(TypeError, local_client._create_class, 'foo',
                        invalid, self.parent_mod)

  def test_invalid_parent(self):
    invalids = [1, 's', [], {}]
    for invalid in invalids:
      self.assertRaises(TypeError, local_client._create_class, 'foo',
                        self.base_class, invalid)

  def test_unicode_name(self):
    cls = local_client._create_class(u'foo', self.base_class, self.parent_mod)
    self.assertEqual('foo', cls.__name__)

  def test_attribute_already_exists(self):
    self.parent_mod.foo = 42
    self.assertRaises(ValueError, local_client._create_class, 'foo',
                      self.base_class, self.parent_mod)


class CreateLoadErrorTestCaseTest(CreateClassTest):
  """Tests for _create_load_error_test_case."""

  def setUp(self):
    self.base_class = unittest.TestCase
    self.parent_mod = types.ModuleType('parent')

  def test_test_method_exists(self):
    module_fullname = 'package.module'
    traceback = 'some traceback method'
    cls = local_client._create_load_error_test_case(module_fullname,
                                                    traceback,
                                                    self.base_class)
    self.assertTrue(hasattr(cls, local_client.MODULE_LOAD_ERROR_METHOD_NAME))


class CreateTestMethodTest(unittest.TestCase):
  """Tests for _create_test_method."""

  def setUp(self):
    parent_mod = types.ModuleType('parent')
    base_class = unittest.TestCase
    self.parent = local_client._create_class('cls', base_class, parent_mod)
    self.comm = local_client.AetaCommunicator('http://www.example.com')

  def test_default(self):
    method = local_client._create_test_method('foo', self.comm, self.parent)
    self.assertEqual(types.FunctionType, type(method))
    method = local_client._create_test_method('foo.bar', self.comm,
                                              self.parent)
    self.assertEqual(types.FunctionType, type(method))

  def test_invalid_parent(self):
    invalids = [1, 's', [], {}]
    for invalid in invalids:
      self.assertRaises(TypeError, local_client._create_test_method, 'foo',
                        self.comm, invalid)

  def test_unicode_name(self):
    method = local_client._create_test_method(u'foo', self.comm, self.parent)
    self.assertEqual('foo', method.__name__)

  def test_class_assigned_to_parent(self):
    self.assertFalse(hasattr(self.parent, 'foo'))
    local_client._create_test_method('foo', self.comm, self.parent)
    self.assertTrue(hasattr(self.parent, 'foo'))

  def test_attribute_already_exists(self):
    self.parent.foo = 42
    self.assertRaises(ValueError, local_client._create_test_method, 'foo',
                      self.comm, self.parent)

  def test_methodName_Is_short_name(self):
    method = local_client._create_test_method('foo', self.comm, self.parent)
    self.assertEqual('foo', method.__name__)
    self.assertTrue(hasattr(self.parent, 'foo'))
    method = local_client._create_test_method('foo.bar', self.comm,
                                              self.parent)
    self.assertEqual('bar', method.__name__)
    self.assertTrue(hasattr(self.parent, 'bar'))


class AetaCommunicatorTest(unittest.TestCase):
  """Tests for AetaCommunicator."""

  def setUp(self):
    self.url = 'http://www.example.com'
    self.comm = local_client.AetaCommunicator(self.url)
    self.orig_get_url_content = local_client._get_url_content

  def tearDown(self):
    local_client._get_url_content = self.orig_get_url_content

  def test_init(self):
    local_client.AetaCommunicator('some random string')
    local_client.AetaCommunicator('some random string',
                                  rest_path='another string')

  def test_get_json_data_without_name(self):
    content = '{"foo": "bar"}'
    local_client._get_url_content = get_mock_get_url_content(content)
    test_data = self.comm._get_rest_data(self.comm.module_path)
    self.assertEqual(content, test_data)

  def test_get_json_data_with_name(self):
    content = '{"foo": "bar"}'
    local_client._get_url_content = get_mock_get_url_content(content)
    test_data = self.comm._get_rest_data(self.comm.module_path,
                                         'some_test_name')
    self.assertEqual(content, test_data)

  def test_get_json_data_with_http_error(self):
    for error_code in [400, 404, 500, 501, 502, 503]:
      local_client._get_url_content = get_mock_get_url_content('', error_code)
      self.assertRaises(local_client.RestApiError, self.comm._get_rest_data,
                        self.comm.module_path)

  def test_get_json_data_with_http_error_500(self):
    server_error_msg = 'server error message'
    local_client._get_url_content = get_mock_get_url_content(self.url, 500,
                                                         server_error_msg)
    error = None
    try:
      self.comm._get_rest_data(self.comm.module_path)
    except local_client.RestApiError, e:
      error = e
    self.assertTrue(self.url in str(error))
    self.assertTrue(server_error_msg in str(error))


  def test_get_test_module_data_converts_json_string(self):
    content = '{"foo": "bar"}'
    local_client._get_url_content = get_mock_get_url_content(content)
    test_data = self.comm.get_test_module_data(self.comm.module_path)
    self.assertEqual({'foo': 'bar'}, test_data)

  def test_get_test_module_data_invalid_json(self):
    content = 'invalid JSON'
    local_client._get_url_content = get_mock_get_url_content(content)
    self.assertRaises(local_client.RestApiError,
                      self.comm.get_test_module_data, self.comm.module_path)

  def test_get_test_result_data_converts_json_string(self):
    content = '{"foo": "bar"}'
    local_client._get_url_content = get_mock_get_url_content(content)
    test_data = self.comm.get_test_result(self.comm.module_path)
    self.assertEqual({'foo': 'bar'}, test_data)


class LoadTestObjectBase(unittest.TestCase):
  """Base class for tests of methods that load test objects."""

  def setUp(self):
    self.comm = local_client.AetaCommunicator('http://www.example.com')
    self.orig_get_url_content = local_client._get_url_content

  def tearDown(self):
    local_client._get_url_content = self.orig_get_url_content


class LoadTestModuleDataTest(LoadTestObjectBase):
  """Tests for _load_test_module_data."""

  def setUp(self):
    super(LoadTestModuleDataTest, self).setUp()
    self.orig_stdout = sys.stdout
    self.my_stdout = StringIO.StringIO()
    sys.stdout = self.my_stdout

  def tearDown(self):
    super(LoadTestModuleDataTest, self).tearDown()
    sys.stdout = self.orig_stdout

  def test_invalid_response_from_rest_api(self):
    local_client._get_url_content = get_mock_get_url_content('[]')
    self.assertRaises(local_client.RestApiError,
                      local_client._load_test_module_data,
                      'foo', self.comm, {}, {})

  def test_fullname_is_a_class(self):
    local_client._get_url_content = get_mock_get_url_content('', 500)
    self.assertRaises(local_client.RestApiError,
                      local_client._load_test_module_data,
                      'foo', self.comm, {}, {})

  def test_loaded_modules_are_stored(self):
    test_objects = {}
    load_tracebacks = {}
    mod_name = 'package.module'
    module_data_str = build_module_data_str(mod_name)
    response = build_test_data_response([module_data_str], [])
    local_client._get_url_content = get_mock_get_url_content(response)
    mod_data, _ = local_client._load_test_module_data('foo', self.comm,
                                                      test_objects,
                                                      load_tracebacks)
    self.assertEqual(1, len(mod_data))
    self.assertTrue(mod_name in mod_data)
    # The parent package is created and stored as well.
    self.assertEqual(2, len(test_objects))
    self.assertTrue(mod_name in test_objects)

  def test_load_error_tracebacks_are_stored(self):
    test_objects = {}
    load_tracebacks = {}
    mod_name = 'package.module'
    load_traceback = 'a traceback string'
    module_data_str = build_module_data_str(mod_name, load_error=True,
                                              load_traceback=load_traceback)
    response = build_test_data_response([module_data_str], [])
    local_client._get_url_content = get_mock_get_url_content(response)
    mod_data, _ = local_client._load_test_module_data('foo', self.comm,
                                                      test_objects,
                                                      load_tracebacks)
    self.assertEqual(0, len(mod_data))
    self.assertTrue(mod_name not in mod_data)
    # No parent package is created and stored when a load error occured.
    self.assertEqual(0, len(test_objects))
    self.assertTrue(mod_name not in test_objects)
    self.assertEqual(1, len(load_tracebacks))
    self.assertTrue(mod_name in load_tracebacks)
    self.assertEqual(load_tracebacks[mod_name], load_traceback)

  def test_multiple_modules_found(self):
    test_objects = {}
    load_tracebacks = {}
    modules = {}
    for name in ['package1.module1', 'package2.module1', 'package2.module2']:
      modules[name] = build_module_data_str(name)
    response = build_test_data_response(modules.values(), [])
    local_client._get_url_content = get_mock_get_url_content(response)
    mod_data, _ = local_client._load_test_module_data('foo', self.comm,
                                                      test_objects,
                                                      load_tracebacks)
    self.assertEqual(3, len(mod_data))
    for name in modules:
      self.assertTrue(name in mod_data)
    # The parent package is created and stored as well.
    self.assertEqual(5, len(test_objects))
    test_object_names = ['package1', 'package1.module1',
                         'package2', 'package2.module1', 'package2.module2']
    for name in test_object_names:
      self.assertTrue(name in test_objects)

  def test_modules_and_subpackages_are_returned(self):
    expected_subpackages = ['sub1', 'sub2', 'sub3']
    response = build_test_data_response([], expected_subpackages)
    local_client._get_url_content = get_mock_get_url_content(response)
    _, subpackages = local_client._load_test_module_data('foo', self.comm,
                                                         {}, {})
    self.assertEqual(len(expected_subpackages), len(subpackages))
    for package in expected_subpackages:
      self.assertTrue(package in subpackages)

  def test_modules_could_not_be_loaded(self):
    mocked_response = 'Could not load module "foo". Some error message.'
    local_client._get_url_content = get_mock_get_url_content(mocked_response)
    _, __ = local_client._load_test_module_data('foo', self.comm, {}, {})
    self.assertTrue('Warning: Could not load module "foo"' in
                    self.my_stdout.getvalue())
    self.assertTrue('Some error message.' in
                    self.my_stdout.getvalue())

class LoadTestModuleTest(LoadTestObjectBase):
  """Tests for _load_test_module."""

  def setUp(self):
    LoadTestObjectBase.setUp(self)
    self.comm = local_client.AetaCommunicator('http://www.example.com')
    self.base_class = unittest.TestCase
    self.orig_load_test_module_data = local_client._load_test_module_data

  def tearDown(self):
    LoadTestObjectBase.tearDown(self)
    local_client._load_test_module_data = self.orig_load_test_module_data

  def test_no_modules_found(self):
    test_objects = {}
    load_tracebacks = {}
    local_client._load_test_module_data = lambda f, c, t, l: ({}, {})
    local_client._load_test_module('foo', self.base_class, self.comm,
                                 test_objects, load_tracebacks)
    self.assertEqual({}, test_objects)
    self.assertEqual({}, load_tracebacks)

  def test_classes_and_methods_correctly_loaded(self):
    test_objects = {}
    load_tracebacks = {}
    mod_name = 'package.module'
    tests = {'TestCase1': ['test_foo', 'test_bar'],
             'TestCase2': ['test_foo', 'test_bar', 'test_baz'],
            }
    module_data_str = build_module_data_str(mod_name, tests)
    response = build_test_data_response([module_data_str], {})
    local_client._get_url_content = get_mock_get_url_content(response)
    local_client._load_test_module('foo', self.base_class, self.comm,
                                 test_objects, load_tracebacks)
    self.assertEqual(9, len(test_objects))
    for class_name, test_methods in tests.items():
      for method_name in test_methods:
        fullname = '%s.%s.%s' % (mod_name, class_name, method_name)
        self.assertTrue(fullname in test_objects)


class LoadTestClassTest(LoadTestObjectBase):
  """Tests for _load_test_class."""

  def setUp(self):
    LoadTestObjectBase.setUp(self)
    self.comm = local_client.AetaCommunicator('http://www.example.com')
    self.base_class = unittest.TestCase
    self.orig_load_test_module_data = local_client._load_test_module_data

  def tearDown(self):
    LoadTestObjectBase.tearDown(self)
    local_client._load_test_module_data = self.orig_load_test_module_data

  def test_module_has_not_been_loaded(self):
    test_objects = {}
    load_tracebacks = {}
    mod_name = 'package.module'
    class_name = 'TestCase'
    fullname = '%s.%s' % (mod_name, class_name)
    tests = {class_name: []}
    module_data_str = build_module_data_str(mod_name, tests)
    response = build_test_data_response([module_data_str], {})
    local_client._get_url_content = get_mock_get_url_content(response)
    local_client._load_test_class(fullname, self.base_class, self.comm,
                                test_objects, load_tracebacks)
    self.assertTrue(fullname in test_objects)
    cls = test_objects[fullname]
    self.assertTrue(issubclass(cls, self.base_class))

  def test_module_has_already_been_loaded(self):
    test_objects = {}
    load_tracebacks = {}
    mod_name = 'package.module'
    class_name = 'TestCase'
    fullname = '%s.%s' % (mod_name, class_name)
    tests = {class_name: []}
    module_data_str = build_module_data_str(mod_name, tests)
    response = build_test_data_response([module_data_str], {})
    local_client._get_url_content = get_mock_get_url_content(response)
    # preload module
    local_client._load_test_module_data(mod_name, self.comm, test_objects,
                                        load_tracebacks)
    # then load the test class
    local_client._load_test_class(fullname, self.base_class, self.comm,
                                test_objects, load_tracebacks)
    self.assertTrue(fullname in test_objects)
    cls = test_objects[fullname]
    self.assertTrue(issubclass(cls, self.base_class))


class LoadTestMethodTest(LoadTestObjectBase):
  """Tests for _load_test_method."""

  def setUp(self):
    LoadTestObjectBase.setUp(self)
    self.comm = local_client.AetaCommunicator('http://www.example.com')
    self.base_class = unittest.TestCase
    self.orig_load_test_module_data = local_client._load_test_module_data

  def tearDown(self):
    LoadTestObjectBase.tearDown(self)
    local_client._load_test_module_data = self.orig_load_test_module_data

  def test_basic_usage(self):
    test_objects = {}
    load_tracebacks = {}
    mod_name = 'package.module'
    class_name = 'TestCase'
    method_name = 'test_foo'
    fullname = '%s.%s.%s' % (mod_name, class_name, method_name)
    tests = {mod_name: [method_name]}
    module_data_str = build_module_data_str(mod_name, tests)
    response = build_test_data_response([module_data_str], {})
    local_client._get_url_content = get_mock_get_url_content(response)
    local_client._load_test_method(fullname, self.base_class, self.comm,
                                 test_objects, load_tracebacks)
    self.assertTrue(fullname in test_objects)


class CreateTestCasesTest(unittest.TestCase):
  """Tests for create_test_casesTest."""

  def setUp(self):
    self.mod_name = 'module'
    self.class_name = 'TestCase'
    self.method_name = 'testFoo'
    self.base_class = unittest.TestCase
    self.mod = types.ModuleType(self.mod_name)
    self.test_class = local_client._create_class(self.class_name,
                                                self.base_class,
                                                self.mod)
    self.orig_get_test_type = local_client.AetaCommunicator.get_test_type
    self.orig_load_test_module_data = local_client._load_test_module_data
    self.orig_load_test_module = local_client._load_test_module
    self.orig_load_test_class = local_client._load_test_class
    self.orig_load_test_metho = local_client._load_test_method

  def tearDown(self):
    local_client.AetaCommunicator.get_test_type = self.orig_get_test_type
    local_client._load_test_module_data = self.orig_load_test_module_data
    local_client._load_test_module = self.orig_load_test_module
    local_client._load_test_class = self.orig_load_test_class
    local_client._load_test_method = self.orig_load_test_metho

  def mock_get_test_type(self, response):
    get_test_type = lambda elf_, testname: response
    local_client.AetaCommunicator.get_test_type = get_test_type

  def test_invalid_arguments(self):
    for obj in [None, 0, [], {}]:
      self.assertRaises(TypeError, local_client.create_test_cases, obj,
                        self.base_class, None)
    for obj in [None, 0, [], {}, '']:
      self.assertRaises(TypeError, local_client.create_test_cases, 'string',
                        obj, None)
    for obj in [0, [], {}]:
      self.assertRaises(TypeError, local_client.create_test_cases, 'string',
                        self.base_class, obj)

  def test_not_existing_test_object(self):
    self.mock_get_test_type('')
    self.assertRaises(local_client.RestApiError,
                      local_client.create_test_cases,
                      'url', self.base_class, 'some prefix')

  def test_different_test_objects(self):
    # Test that different loader functions are called for different
    # test types and loaded test objects are returned.

    # allow unused variables - pylint: disable-msg=W0613
    def mock_load_test_object(prefix, cls, comm, test_objects, tracebacks):
      test_objects[self.class_name] = self.test_class

    type_function_mapping = {'package': '_load_test_module',
                             'module': '_load_test_module',
                             'class': '_load_test_class',
                             'method': '_load_test_method',
                            }

    for test_type, func_name in type_function_mapping.items():
      self.mock_get_test_type(test_type)
      orig_func = getattr(local_client, func_name)
      setattr(local_client, func_name, mock_load_test_object)
      test_cases = local_client.create_test_cases('url', self.base_class,
                                                'some.test.object')
      self.assertTrue(self.test_class in test_cases)
      setattr(local_client, func_name, orig_func)

  def test_with_load_errors(self):

    # allow unused variables - pylint: disable-msg=W0613
    def mock_load_test_object(prefix, cls, comm, test_objects, tracebacks):
      tracebacks[self.class_name] = self.test_class

    self.mock_get_test_type('class')
    setattr(local_client, '_load_test_class', mock_load_test_object)
    test_cases = local_client.create_test_cases('url', self.base_class,
                                                'some.test.object')
    self.assertEqual(1, len(test_cases))


class AddTestCasesToModuleTest(unittest.TestCase):
  """Tests for add_test_cases_to_moduleTest."""

  def setUp(self):
    self.base_class = unittest.TestCase

  def test_invalid_arguments(self):
    mod = types.ModuleType('module')
    for obj in [None, '', 0, {}, ()]:
      self.assertRaises(TypeError, local_client.add_test_cases_to_module,
                        obj, mod)
      self.assertRaises(TypeError, local_client.add_test_cases_to_module,
                        [], obj)

  def test_no_test_cases(self):
    # Test that no test cases are added to a module if no test cases
    # are passed.
    mod = types.ModuleType('module')
    local_client.add_test_cases_to_module([], mod)
    for attr_name in dir(mod):
      attr = getattr(mod, attr_name)
      self.assertFalse(isinstance(attr, type))
      self.assertFalse(isinstance(attr, types.ClassType))

  def test_test_cases_are_added(self):
    test_mod = types.ModuleType('test_module')
    names = ['TestCase1', 'TestCase2', 'TestCase3']
    parent_mod = types.ModuleType('parent_module')
    test_cases = []
    for name in names:
      test_case = local_client._create_class(name, self.base_class, parent_mod)
      test_cases.append(test_case)
    local_client.add_test_cases_to_module(test_cases, test_mod)
    for i, name in enumerate(names):
      self.assertTrue(hasattr(test_mod, name))
      self.assertEqual(test_cases[i], getattr(test_mod, name))

  def test_attributes_already_exist(self):
    test_mod = types.ModuleType('test_module')
    parent_mod = types.ModuleType('parent_module')
    test_case = local_client._create_class('TestCase', self.base_class,
                                           parent_mod)
    local_client.add_test_cases_to_module([test_case], test_mod)
    self.assertRaises(ValueError, local_client.add_test_cases_to_module,
                      [test_case], test_mod)
