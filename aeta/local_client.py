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

"""Module that generates local tests for remote aeta-enabled applications.

In addition, this module can also be invoked as a stand-alone
commandline interface for aeta-enabled App Engine applications.

Interaction with aeta-enabled application is done via the aeta REST
interface. This interface is used to extract information about tests
(such as provided test classes) and to trigger tests and return the
corresponding results.

The basic workflow is like this:
1) Retrieve information about remote test objects.
2) Construct a local representation of those test objects, including
   parent packages, modules, classes, and test methods.
3) Run local tests (which invoke remote tests and report their outcome).

The constructed local test methods communicate with the aeta REST
interface. They trigger tests remotely and then report back the
outcame (pass for successful tests, raised test assertion for failed
tests, and errors for invalid tests).

If you this module is used as a library, a base class for tests has to
be provided. Usually this is unittest.TestCase, but any other
TestCase-derived class can be used. This allows the integration into
existing test infrastructures.

"""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

import inspect
import optparse
import os
import sys
import types
import unittest
import urllib2

try:
  import json
except ImportError:
  import simplejson as json

# json.decoder.JSONDecodeError has not been introduced before 2.0
try:
  # pylint:disable-msg=E1101
  JSON_DECODE_ERROR = json.decoder.JSONDecodeError
except AttributeError:
  JSON_DECODE_ERROR = ValueError


__all__ = ['Error',
           'RestApiError',
           'TestError',
           'AetaCommunicator',
           'CreateTestCases',
           'AddTestCasesToModule',
          ]


USAGE = """usage: %prog AETA_URL [TESTNAME]

AETA_URL         URL which is handled by the aeta library.
TESTNAME_PREFIX  Optional prefix of all tests to run, e.g. a package name."""

# To indicate that a test module could not be loaded successfully, we
# create a test which raises TestError when executed. Name of the
# class and the test method are defined here.
MODULE_LOAD_ERROR_CLASS_NAME = 'ModuleLoadTest'
MODULE_LOAD_ERROR_METHOD_NAME = 'testModuleLoadedSuccessfully'

# Path in REST interface where test module information is provided.
_REST_MODULE_PATH = 'modules'
# Path in REST interface where test result information is provided.
_REST_RESULT_PATH = 'results'
# Path in REST interface where test object type information is provided.
_REST_TYPE_PATH = 'objecttype'
# Name of attribute in module information that holds the actual module data.
_REST_MOD_DATA_DATA_ATTR_KEY = 'module_data'
# Name of attribute in module information that holds names of all subpackages.
_REST_MOD_DATA_SUBPACKAGES_ATTR_KEY = 'subpackages'



class Error(Exception):
  """Base aeta local_client error type."""


class RestApiError(Error):
  """Raised when using the REST API caused an error."""


class TestError(Error):
  """Raised by tests which raised an error."""


# it's a data container essentially - pylint:disable-msg=R0903
class _TestModuleData(object):
  """Container for available information about a test module."""

  # pylint:disable-msg=C0103
  @staticmethod
  def load_from_dict(d):
    """Create a _TestModuleData object from a dictionary object.

    Only dictionary entries which keys correspond to attributes of
    this class are loaded.

    Args:
      d: dict object with attributes as key-value pairs.

    Returns:
      A _TestModuleData object.
    """
    mod_data = _TestModuleData()
    for key, value in d.items():
      # Convert unicode to str - no unicode attribute names accepted.
      str_key = str(key)
      if hasattr(mod_data, str_key):
        setattr(mod_data, str_key, value)
    return mod_data

  def __init__(self):
    self.fullname = None
    self.load_traceback = None
    # key = test class name, value = a list of test methods for this class.
    self.tests = {}


def _get_url_content(url):
  """Retrieve content provided at the given URL.

  This function's main purpose is to help testing by mocking HTTP
  responses.

  Args:
    url: URL from where content should be fetched.

  Returns:
     The content served at the given URL.
  """
  resp = urllib2.urlopen(url)
  return resp.read()


def _create_module(name, parent=None):
  """Create a module object.

  If you provide a parent module, the newly created child module will
  be added as an attribute to the parent.

  Args:
    name: Name of the module.
    parent: Optional parent module.

  Returns:
    A module object.

  Raises:
    TypeError: If the parent module is not a module
    ValueError: If the parent module already has an attribute with this name.
  """
  name = str(name)
  module = types.ModuleType(name)
  if parent is not None:
    if not isinstance(parent, types.ModuleType):
      raise TypeError('"parent" must be a module.')
    if hasattr(parent, name):
      raise ValueError('"parent" already has an attribute "%s".' % name)
    setattr(parent, name, module)
  return module


def _create_class(name, base_class, parent):
  """Create a class object.

  Args:
    name: Name of the new class.
    base_class: Class which will be used as base class to the new class.
    parent: Parent module the class will be attached to.

  Returns:
    A class object.

  Raises:
    TypeError: If the parent module is not a module or base_class is not a
               class.
    ValueError: If the parent module already has an attribute with this name.
  """
  if not isinstance(base_class, type) and not isinstance(base_class,
                                                         types.ClassType):
    raise TypeError('"base_class" must be class.')
  name = str(name)

  # doesn't need a docstring - pylint:disable-msg=C0111,W0232
  class NewClass(base_class):
    pass

  NewClass.__name__ = name
  if not isinstance(parent, types.ModuleType):
    raise TypeError('"parent" must be a module.')
  if hasattr(parent, name):
    raise ValueError('"parent" already has an attribute "%s".' % name)
  setattr(parent, name, NewClass)
  return NewClass


def _create_load_error_test_case(fullname, traceback, base_class):
  """Create a test case for remote module load errors.

  Args:
    fullname: Full name of the module which could not be loaded.
    traceback: Traceback of the load error.
    base_class: Base class of the test case which will be created.

  Returns:
    A test case with a single test method that raises a TestError.

  Raises:
    TypeError: If base_class is not a class.
  """
  if not isinstance(base_class, type) and not isinstance(base_class,
                                                         types.ClassType):
    raise TypeError('"base_class" must be class.')
  module = _create_module(fullname)
  class_name = '%s.%s' % (fullname, MODULE_LOAD_ERROR_CLASS_NAME)
  new_class = _create_class(class_name, base_class, module)

  # doesn't need a docstring, dude - pylint:disable-msg=C0111,W0613,
  def test_method(self):
    raise TestError(traceback)

  setattr(new_class, MODULE_LOAD_ERROR_METHOD_NAME, test_method)
  return new_class


def _create_test_method(fullname, aeta_communicator, parent):
  """Create a test method object which fetches the test result via aeta.

  The created test method assumes that the parent object provides the
  usual unittest.TestCase assert methods.

  Args:
    fullname: Full name of the test method it has on the server-side.
    aeta_communicator: An AetaCommunicator instance.
    parent: Parent class the method will be assigned to.

  Returns:
    A test method object.

  Raises:
    TypeError: If the parent class is not a class.
    ValueError: If the parent class already has an attribute of the given name.
  """
  fullname = str(fullname)
  if not isinstance(parent, type) and not isinstance(parent, types.ClassType):
    raise TypeError('"parent" must be a type.')
  if hasattr(parent, fullname):
    raise ValueError('"parent" already has an attribute "%s".' % fullname)

  # No docstring because unittest uses method name - pylint:disable-msg=C0111
  def test_method(self):
    result_list = aeta_communicator.get_test_result(fullname)
    if len(result_list) != 1:
      raise RestApiError('Expected exactly 1 test result, but got %s for "%s"'
                         % (len(result_list), fullname))
    result = result_list[0]
    # Lists of errors and failures that were raised by this test.
    errors = result['errors']
    failed = result['failures']
    # If either list is not empty, display the traceback.
    if errors:
      raise TestError(result['errors'][0][1])
    if failed:
      self.assertFalse(failed, result['failures'][0][1])

  # This is used by testing framework - pylint: disable-msg=W0612,W0621
  shortname = fullname.split('.')[-1]
  # redefining __name__ is cool here - pylint:disable-msg=W0622
  test_method.__name__ = shortname
  setattr(parent, shortname, test_method)
  return test_method


class AetaCommunicator(object):
  """Class which communicates with the aeta REST interface."""

  def __init__(self, aeta_url, rest_path='rest'):
    """Initializer.

    Args:
      aeta_url: URL handled by the aeta library.
      rest_path: Path suffix to aeta_path which answers REST requests.
    """
    rest_path = '%s/%s/' % (aeta_url.strip('/'), rest_path.strip('/'))
    self.module_path = rest_path + _REST_MODULE_PATH
    self.result_path = rest_path + _REST_RESULT_PATH
    self.type_path = rest_path + _REST_TYPE_PATH
    self._module_data_cache = {}
    self._result_data_cache = {}

  # shouldn't be a function - pylint:disable-msg=R0201
  def _get_rest_data(self, url_prefix, testname=None):
    """Retrieve data from aeta REST interface.

    Args:
      url_prefix: URL prefix where data is provided.
      testname: Name of the test object to retrieve data for.

    Returns:
      An object with test data as returned by the aeta REST interface.
    """
    url = url_prefix
    if testname is not None:
      url += '/' + testname
    rest_response = ''
    try:
      rest_response = _get_url_content(url)
    except urllib2.HTTPError, err:
      error_message = err.read()
      if err.code == 400 or err.code == 404:
        msg = 'No data for "%s" found.' % testname
      elif err.code == 500:
        msg = ('The server returned a 500 and the following error message '
               'while accessing "%s". Please check the server logs for '
               'more details. Error message: %s"""%s"""' % (url, os.linesep,
                                                            error_message))
      else:
        msg = 'An error occured while fetching data for "%s":' % testname
        msg += '%s"""%s"""' % (os.linesep, error_message)
      raise RestApiError(msg)
    return rest_response

  def get_test_module_data(self, testname=None):
    """Retrieve test module data.

    If no testname is specified, all available test module data is
    retrieved. This can be an expensive operation which for large test
    suites is likely to hit the 30 second request limit of App Engine.

    Args:
      testname: Name of test module/package to retrieve test information for.

    Returns:
      An object with test data as returned by the aeta REST interface.
    """
    if testname in self._module_data_cache:
      return self._module_data_cache[testname]
    response = self._get_rest_data(self.module_path, testname)
    try:
      testdata = json.loads(response)
    except JSON_DECODE_ERROR:
      msg = 'Could not decode message: %s%s' % (os.linesep, response)
      raise RestApiError(msg)
    self._module_data_cache[testname] = testdata
    return testdata

  def get_test_result(self, testname):
    """Retrieve test result for test object.

    If no testname is specified, test results from all available tests
    are retrieved. This can be an expensive operation which for large
    test suites is likely to hit the 30 second request limit of App
    Engine.

    Args:
      testname: Name of the test object.

    Returns:
      An object with test result data as returned by the aeta REST interface.
    """
    if testname in self._result_data_cache:
      return self._result_data_cache[testname]
    response = self._get_rest_data(self.result_path, testname)
    testresult = json.loads(response)
    self._result_data_cache[testname] = testresult
    return testresult

  def get_test_type(self, testname):
    """Retrieve the type of a test object.

    Possible types are 'package', 'module', 'class', and 'method'.  If
    testname does not represent a valid test object, an empty string
    is returned.

    Args:
      testname: Name of the test object.

    Returns:
      The type of a test object as string.
    """
    return self._get_rest_data(self.type_path, testname)


# lots of local variables, maybe fix later - pylint:disable-msg=R0914
def _load_test_module_data(fullname, comm, test_objects, load_tracebacks):
  """Load test module data from remote aeta-enabled app.

  This function will modify the content of 'test_objects' and
  'load_tracebacks'. Every encountered test module is created and then
  added to 'test_objects', loading errors are stored in
  'load_tracebacks', whereas values are identified by the test objects
  full name.

  Subpackages, test classes and test method are not created by this
  function.

  Args:
    fullname: The full name of the test module or package to load.
    comm: An AetaCommunicator instance.
    test_objects: A dictionary of all loaded test objects.
    load_tracebacks: A dictionary of module loading error tracebacks.

  Returns:
    A (mod_data_dict, subpackages) tuple, 'mod_data_dict' being a
    dictionary of (module name, _TestModuleData) pairs and 'subpackages' a
    list of subpackages of the loaded package.

  Raises:
    RestApiError: If no module is found for the given fullname.
  """
  mod_data_dict = {}
  subpackages = []
  try:
    raw_testmodule_data = comm.get_test_module_data(fullname)
  except RestApiError, err:
    if str(err).find('Could not load module') >= 0:
      print 'Warning: Could not load module "%s"' % fullname
      print str(err)
      return mod_data_dict, subpackages
    else:
      raise
  if not _REST_MOD_DATA_DATA_ATTR_KEY in raw_testmodule_data:
    raise RestApiError('No module data found for "%s"' % fullname)
  for raw_mod_data in raw_testmodule_data[_REST_MOD_DATA_DATA_ATTR_KEY]:
    mod_data = _TestModuleData.load_from_dict(raw_mod_data)
    name_parts = mod_data.fullname.split('.')
    if mod_data.load_traceback:
      load_tracebacks[mod_data.fullname] = mod_data.load_traceback
      continue
    if len(name_parts) > 1:
      # Create parent packages.
      for i, name in enumerate(name_parts[:-1]):
        parent_fullname = '.'.join(name_parts[:i])
        if parent_fullname in test_objects:
          continue
        parent_package = test_objects.get(parent_fullname, None)
        module = _create_module(name, parent=parent_package)
        own_fullname = '.'.join(name_parts[:i+1])
        test_objects[own_fullname] = module
    else:
      parent_package = None
    mod_data_dict[mod_data.fullname] = mod_data
    module = _create_module(mod_data.fullname, parent=parent_package)
    test_objects[mod_data.fullname] = module
  if _REST_MOD_DATA_SUBPACKAGES_ATTR_KEY in raw_testmodule_data:
    subpackages = raw_testmodule_data[_REST_MOD_DATA_SUBPACKAGES_ATTR_KEY]
  return mod_data_dict, subpackages


def _load_test_module(fullname, base_class, comm, test_objects,
                      load_tracebacks):
  """Load test module with the name given in fullname.

  This function will modify the content of 'test_objects' and
  'load_tracebacks'. Test objects are stored in 'test_objects',
  loading errors are stored in 'load_tracebacks'.

  All encountered subpackages, modules, test classes and methods are
  loaded recursively.

  Args:
    fullname: The full name of the test module or package to load.
    base_class: Base class used for created test cases.
    comm: An AetaCommunicator instance.
    test_objects: A dictionary of all loaded test objects.
    load_tracebacks: A dictionary of module loading error tracebacks.
  """
  mod_data_dict, subpackages = _load_test_module_data(fullname,
                                                      comm,
                                                      test_objects,
                                                      load_tracebacks)
  for mod_name, mod_data in mod_data_dict.items():
    if mod_data.tests:
      for test_class, methods in mod_data.tests.items():
        class_name = '.'.join([mod_name, test_class])
        _load_test_class(class_name, base_class, comm, test_objects,
                         load_tracebacks)
        for method in methods:
          method_name = '.'.join([class_name, method])
          _load_test_method(method_name, base_class, comm, test_objects,
                            load_tracebacks)
  for subpackage_name in subpackages:
    sub_name = '.'.join([fullname, subpackage_name])
    _load_test_module(sub_name, base_class, comm, test_objects,
                    load_tracebacks)


def _load_test_class(fullname, base_class, comm, test_objects,
                     load_tracebacks):
  """Load test class with the name given in fullname.

  Test methods are not recursively created iff the parent module of
  the class already exists. This was done to reduce redundant
  roundtrips to remote apps.

  This function will modify the content of 'test_objects' and
  'load_tracebacks'. Test objects are stored in 'test_objects',
  loading errors are stored in 'load_tracebacks'.

  Args:
    fullname: The full name of the test class to load.
    base_class: Base class used for created test cases.
    comm: An AetaCommunicator instance.
    test_objects: A dictionary of all loaded test objects.
    load_tracebacks: A dictionary of module loading error tracebacks.
  """
  mod_name = '.'.join(fullname.split('.')[:-1])
  if mod_name not in test_objects:
    mod_data_dict, _ = _load_test_module_data(mod_name, comm, test_objects,
                                              load_tracebacks)
    mod_data = mod_data_dict[mod_name]
    for test_class, methods in mod_data.tests.items():
      if '.'.join([mod_data.fullname, test_class]) != fullname:
        continue
      class_name = '.'.join([mod_data.fullname, test_class])
      _load_test_class(class_name, base_class, comm, test_objects,
                       load_tracebacks)
      for method in methods:
        method_name = '.'.join([class_name, method])
        new_method = _create_test_method(method_name, comm,
                                         test_objects[class_name])
        test_objects[method_name] = new_method
  else:
    new_class = _create_class(fullname, base_class,
                             test_objects[mod_name])
    test_objects[fullname] = new_class


def _load_test_method(fullname, base_class, comm, test_objects,
                      load_tracebacks):
  """Load test method with the name given in fullname.

  This function will modify the content of 'test_objects' and
  'load_tracebacks'. Test objects are stored in 'test_objects',
  loading errors are stored in 'load_tracebacks'.

  Args:
    fullname: The full name of the test method to load.
    base_class: Base class used for created test cases.
    comm: An AetaCommunicator instance.
    test_objects: A dictionary of all loaded test objects.
    load_tracebacks: A dictionary of module loading error tracebacks.
  """
  name_parts = fullname.split('.')
  mod_name = '.'.join(name_parts[:-2])
  class_name = '.'.join(name_parts[:-1])
  _load_test_module_data(mod_name, comm, test_objects, load_tracebacks)
  if class_name not in test_objects:
    new_class = _create_class(class_name, base_class,
                              test_objects[mod_name])
    test_objects[class_name] = new_class
  new_method = _create_test_method(fullname, comm,
                                   test_objects[class_name])
  test_objects[fullname] = new_method


def create_test_cases(aeta_url, base_class, testname_prefix=None):
  """Create local test cases for an aeta-enabled application.

  Args:
    aeta_url: URL where an aeta instance is available.
    base_class: Base class for all generated test cases.
    testname_prefix: Optional name prefix for tests to be created.

  Returns:
    A list of test cases derived from base_class.

  Raises:
    TypeError: If any of the input parameter is of an incorrect type.
    RestApiError: If prefix does not specify a valid test object.
  """
  if not isinstance(aeta_url, basestring):
    raise TypeError('"aeta_url" must be a string, not %s' % type(aeta_url))
  if not isinstance(base_class, type) and not isinstance(base_class,
                                                         types.ClassType):
    raise TypeError('"base_class" must be class.')
  if (testname_prefix is not None and
      not isinstance(testname_prefix, basestring)):
    raise TypeError('"testname_prefix" must be None or a string, not %s' %
                    type(testname_prefix))
  # A dictionary of all loaded test objects.
  test_objects = {}
  # A dictionary of all encountered load error tracebacks.
  load_tracebacks = {}
  comm = AetaCommunicator(aeta_url)
  testname_prefixes = []
  if testname_prefix:
    test_type = comm.get_test_type(testname_prefix)
    if not test_type and testname_prefix:
      raise RestApiError('"%s" does not seem to be a valid test object' %
                         testname_prefix)
    testname_prefixes = [testname_prefix]
  else:
    (mod_data_dict, subpackages) = _load_test_module_data('', comm,
                                                          test_objects,
                                                          load_tracebacks)
    testname_prefixes.extend(mod_data_dict.keys())
    testname_prefixes.extend(subpackages)
  for prefix in testname_prefixes:
    test_type = comm.get_test_type(prefix)
    if test_type in ['package', 'module']:
      _load_test_module(prefix, base_class, comm, test_objects,
                        load_tracebacks)
    if test_type == 'class':
      _load_test_class(prefix, base_class, comm, test_objects, load_tracebacks)
    if test_type == 'method':
      _load_test_method(prefix, base_class, comm, test_objects,
                        load_tracebacks)
  test_classes = [o for o in test_objects.values() if isinstance(o, type)]
  for module_name, traceback in load_tracebacks.items():
    test_class = _create_load_error_test_case(module_name, traceback,
                                              base_class)
    test_classes.append(test_class)
  return test_classes


def add_test_cases_to_module(testcases, module):
  """Add test cases to the given module.

  Args:
    testcases: A list of test cases.
    module: The module the test cases should be added to.

  Raises:
    TypeError: If one of the input parameters is of an incorrect type.
    ValueError: If the module already has an attribute with a name of
                one of the test cases.
  """
  if not isinstance(testcases, list):
    raise TypeError('"testcases" must be a list, not a %s' % type(testcases))
  if not isinstance(module, types.ModuleType):
    raise TypeError('"module" must be a module, not a %s' % type(module))
  for testcase in testcases:
    if hasattr(module, testcase.__name__):
      raise ValueError('Class "%s" already has an attribute called '
                       '"%s"' % (module.__name__, testcase.__name__))
    setattr(module, testcase.__name__, testcase)


def main(aeta_url, testname_prefix=None):
  """Main function invoked if module is run from commandline.

  Args:
    aeta_url: URL where an aeta instance is available.
    testname_prefix: Optional name prefix for tests to be created.
  """
  this_module = inspect.getmodule(main)
  suite = unittest.TestSuite()
  testcases = create_test_cases(aeta_url, unittest.TestCase, testname_prefix)
  add_test_cases_to_module(testcases, this_module)
  suite = unittest.TestLoader().loadTestsFromModule(this_module)
  if not suite.countTestCases():
    error_msg = 'No tests '
    if testname_prefix:
      error_msg += 'with the prefix "%s" ' % testname_prefix
    error_msg += 'found at "%s"' % aeta_url
    print >> sys.stderr, error_msg
    sys.exit(1)
  unittest.TextTestRunner(verbosity=2).run(suite)
  for testcase in testcases:
    delattr(this_module, testcase.__name__)


if __name__ == '__main__':
  PARSER = optparse.OptionParser(USAGE)
  (OPTIONS, ARGS) = PARSER.parse_args()
  if not ARGS or len(ARGS) > 2:
    print USAGE
    sys.exit(1)
  INPUT_AETA_URL = ARGS[0]
  INPUT_TESTNAME_PREFIX = None
  if len(ARGS) == 2:
    INPUT_TESTNAME_PREFIX = ARGS[1]
  main(INPUT_AETA_URL, INPUT_TESTNAME_PREFIX)
