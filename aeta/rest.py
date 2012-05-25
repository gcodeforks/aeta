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

"""REST interface to the App Engine test extension (aeta).

The REST interface will respond to request regarding test objects.  A
test object can be a package, a module, a class, or a test method. The
name pattern used is similar to the standard Python pattern which
describes a hierarchy such as package.subpackage.module.class.method.

The interface has the following top level paths:
- modules/<fullname>
- results/<fullname>
- objecttype/<fullname>

For all requests, a full object name (according to the pattern
described above) is expected to follow the top level path. All
requests will respond with a JSON object or an HTTP error, e.g. if a
particular object could not be found.


Module Information
------------------

Requests to an URL with the 'modules' prefix will return test
information on the requested module or package. The format of a
response is

{ module_data: an array of module data (defined below),
  subpackages: an array of subpackage names
}

module data has the following structure:

{'fullname': full name of a package of module,
 'tests': a dictionary with test classes as key values, and a list of
          test method names,
 'load_error': false if the object could be loaded, true if an error
               occured,
 'load_traceback': the traceback of the load error or null ,
}


Test results
------------

Requests to an URL with the 'results' prefix will return a list of
test result information for all tests defined in and below the
particular test object. The highest abstraction level for returned
test result information is module, the lowest is method. For example,
if the object is a package, all tests defined in this package and
subpackages will be grouped by the module they belong to and
returned. If the object is a class, only one test result is returned,
describing the outcome of running all tests of this particular
class.

This can be useful if tests you have to run will hit the timeout
imposed by App Engine. If running a particular test case would take 1
minute, but the limit is at 30 seconds, you can thus run each test
method individually and bypass this limitation.

The format of results is:

[{'fullname': full name of the test object,
  'errors': An array of [test suite name, error traceback] arrays of
            all test cases which caused an error,
  'failures': An array of [test name suite, error traceback] arrays of
              all test cases which failed,
  'passed': The number of passed tests,
  'testsRun': the total number of tests run,
  'output': cgi-escaped output of the entire test run,
 }]


Testobject Type
---------------

Finally, requests to an URL with the "objecttype" prefix return the
type of the test object the given fullname represents. Possible types
(and therefore return values) are "package", "module", "class", and
"method". If the given fullname does not represent any of those, an
empty string is returned.
"""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

import cgi
import cStringIO
import glob
import inspect
import logging
import os
import sys

import simplejson as json

from aeta import config
from aeta import handlers
from aeta import logic
from aeta import models


class Error(Exception):
  """Base rest error type."""


class ObjectNotFoundError(Exception):
  """Raised when a particular test object could not be found."""
  pass


class LoadError(Error):
  """Raised when a module could not be loaded."""
  pass


class IncorrectUsageError(Error):
  """Raised when the REST API is used incorrectly."""
  pass


def convert_module_data(module_data):
  """Convert module data to JSON format.

  Args:
    module_data: A models.ModuleData object.

  Returns:
    A jsonized representation of the passed module data object.
  """
  logic.check_type(module_data, 'module_data', models.ModuleData)
  data = {'fullname': module_data.fullname,
          'load_error': module_data.load_error,
          'load_traceback': module_data.load_traceback,
          'tests': module_data.tests,
         }
  return json.dumps(data)


def convert_test_result_data(result_data):
  """Convert test result data to JSON format.

  Args:
    result_data: A models.TestResultData object.

  Returns:
    A jsonized representation of the passed testresults object.
  """
  logic.check_type(result_data, 'result_data', models.TestResultData)
  errors = [(str(error), info) for (error, info) in result_data.errors]
  failures = [(str(failure), info) for (failure, info) in result_data.failures]
  data = {'errors': errors,
          'failures': failures,
          'fullname': result_data.fullname,
          'output': cgi.escape(result_data.output),
          'passed': result_data.passed,
          'testsRun': result_data.testsRun,
         }
  return json.dumps(data)


def get_subpackages(fullname):
  """Get all subpackages of fullname.

  Only children are returned, no grandchildren or below.

  If fullname does not identify a valid package, an empty list is
  returned.

  Args:
    fullname: Name of the parent package.

  Returns:
    A list of subpackages of the specified package.
  """
  logic.check_type(fullname, 'fullname', str)
  packages = []
  path = logic.get_abs_path_from_package_name(fullname)
  if not path:
    return []
  for directory in glob.glob(os.path.join(path, '*')):
    if os.path.isdir(directory):
      if (os.path.isfile(os.path.join(directory, '__init__.py')) or
          os.path.isfile(os.path.join(directory, '__init__.pyc'))):
        packages.append(os.path.basename(directory))
  return packages


def jsonize_module_information(module_data, subpackages=None):
  """Create JSON data for package/module information.

  Modules and packages are treated equally with the difference, that
  packages have subpackages whereas modules do not.

  Args:u
    module_data: A list of models.ModuleData objects.
    subpackages: A list of subpackages or None if no subpackages are available.

  Returns:
    A jsonized dictionary with both inputs as key value pairs.
  """
  logic.check_type(module_data, 'module_data', list)
  if subpackages is None:
    subpackages = []
  logic.check_type(subpackages, 'subpackages', list)
  jsonized_pckgs = json.dumps(subpackages)
  converted_moddata = []
  for data in module_data:
    converted_moddata.append(convert_module_data(data))
  jsonized_moddata = '[' + ','.join(converted_moddata) + ']'
  return '{"subpackages": %s, "module_data": %s}' % (jsonized_pckgs,
                                                     jsonized_moddata)


def get_module_data(fullname, conf):
  """Get module data for fullname.

  Modules and packages are treated equally with the difference, that
  packages have subpackages whereas modules do not.

  Args:
    fullname: Name of a module or package.
    conf: A config.Config instance.

  Returns:
    A ([subpackages list], [moduledata list]) tuple.

  Raises:
    ObjectNotFoundError: If no corresponding object could be found.
    LoadError: If a module could not be loaded.
    IncorrectUsageError: If an test object which is not a module or package
                         was requested.
  """
  logic.check_type(fullname, 'fullname', str)
  subpackages = []
  moduledata = []
  modules = []
  load_errors = []
  if not fullname:
    # If no test is specified, return all available top-level test
    # objects.
    for name in conf.test_package_names:
      if logic.get_abs_path_from_package_name(name):
        subpackages.append(name)
      elif logic.is_module(name):
        modules.extend(logic.load_modules(
            name,
            load_errors,
            module_pattern=conf.test_module_pattern,
            depth=1))
    moduledata = logic.create_module_data(modules, load_errors)
    return  (subpackages, moduledata)
  obj = logic.get_requested_object(fullname)
  # We cannot return module data for classes or methods.
  if inspect.isclass(obj):
    raise IncorrectUsageError('No module information for a class '
                              'can be provided.')
  if inspect.ismethod(obj):
    raise IncorrectUsageError('No module information for a method '
                              'can be provided.')
  elif logic.get_abs_path_from_package_name(fullname):
    subpackages = get_subpackages(fullname)
    modules.extend(logic.load_modules(fullname, load_errors,
                                      module_pattern=conf.test_module_pattern,
                                      depth=1))
  elif inspect.ismodule(obj):
    modules.append(logic.load_module_from_module_name(fullname, load_errors))
  elif obj is None:
    # TODO(schuppe): This approach is not able to distinguish
    # ImportErrors which occur because the module has incorrect
    # imports or the module itself does not exist. Both case raise an
    # ImportError, although the latter should map to 'no such test
    # object found.'
    moduledata = logic.load_module_from_module_name(fullname, load_errors)
    if not load_errors:
      raise ObjectNotFoundError('No test object "%s" found.' % fullname)
    else:
      stacktrace = load_errors[0][1]
      raise LoadError('Could not load module "%s": %s' % (fullname,
                                                          stacktrace))
  moduledata = logic.create_module_data(modules, load_errors)
  return (subpackages, moduledata)


# acceptable number of branches - pylint:disable-msg=R0912
def get_test_result_data(fullname, conf):
  """Get all test results for fullname.

  Args:
    fullname: Name of a test object such as a package or a test case.
    conf: A config.Config instance.

  Returns:
    A list of models.TestResultData objects.

  Raises:
    ObjectNotFoundError: If no corresponding object could be found.
  """
  logic.check_type(fullname, 'fullname', str)
  modules = []
  results = []
  if not fullname:
    for testname in conf.test_package_names:
      modules.extend(logic.load_modules(
          testname,
          [],
          module_pattern=conf.test_module_pattern))
    for module in modules:
      results.append(logic.run_test(module))
  elif logic.get_abs_path_from_package_name(fullname):
    modules = logic.load_modules(
        fullname,
        [],
        module_pattern=conf.test_module_pattern)
    for module in modules:
      results.append(logic.run_test(module))
  if results:
    return results
  obj = logic.get_requested_object(fullname)
  if obj is None:
    raise ObjectNotFoundError('There is no such object: "%s"' % fullname)
  elif inspect.ismodule(obj):
    modules = [obj]
    for module in modules:
      result = logic.run_test(module)
      results.append(result)
  elif inspect.isclass(obj):
    result = logic.run_test(obj)
    if result:
      results.append(result)
  elif inspect.ismethod(obj):
    result = logic.run_test(obj)
    if result:
      results.append(result)
  return results


def get_object_type(fullname):
  """Get a string indicating the type of the test object.

  Valid object types are 'package', 'module', 'class', and
  'method'. If fullname cannot be mapped to a valid test object of one
  of these for kinds, an empty string is returned.

  Args:
    fullname: Name of a test object such as a package or a test casex.

  Returns:
    A string indicating the type of the object.
  """
  if not fullname:
    return ''
  if logic.get_abs_path_from_package_name(fullname):
    return 'package'
  obj = logic.get_requested_object(fullname)
  if inspect.ismodule(obj):
    return 'module'
  if inspect.isclass(obj):
    return 'class'
  if inspect.ismethod(obj):
    return 'method'
  return ''


class BaseRESTRequestHandler(handlers.BaseRequestHandler):
  """Request handler for REST API."""

  def render_error(self, msg, status):
    """Write an error message to self.response.

    Args:
      msg: The content of the response.
      status: The status code of the response.
    """
    self.response.out.write(msg)
    self.response.set_status(status)


class ModuleInfoRequestHandler(BaseRESTRequestHandler):
  """Request handler for module information requests."""

  # conscious change in argument count - pylint:disable-msg=W0221
  def get(self, fullname):
    """Render jsonized package or module information.

    Args:
      fullname: Name of a package or module.

    Returns:
      A String containing jsonized package or module information.
    """
    conf = config.get_config()
    try:
      try:
        old_stdout = sys.stdout
        sys.stdout = cStringIO.StringIO()
        (subpackages, moduledata) = get_module_data(fullname, conf)
      finally:
        stdout = sys.stdout.getvalue()
        if stdout:
          logging.info("stdout: %s", stdout)
        sys.stdout = old_stdout
    except IncorrectUsageError, err:
      self.render_error(err.message, 404)
      return
    except ObjectNotFoundError, err:
      self.render_error(err.message, 404)
      return
    except LoadError, err:
      logging.error(err)
      self.render_error(str(err), 500)
      return
    jsonized_info = jsonize_module_information(moduledata, subpackages)
    self.response.out.write(jsonized_info)


class TestResultRequestHandler(BaseRESTRequestHandler):
  """Request handler for test result requests."""

  # conscious change in argument count - pylint:disable-msg=W0221
  def get(self, fullname):
    """Render jsonized test results.

    Args:
      fullname: Name of a test object.

    Returns:
      A String containing jsonized test results.
    """
    conf = config.get_config()
    try:
      results = get_test_result_data(fullname, conf)
    except ObjectNotFoundError, err:
      self.render_error(str(err), 404)
      logging.error(err)
      return
    converts = []
    for result in results:
      converts.append(convert_test_result_data(result))
    self.response.out.write('[' + ','.join(converts) + ']')


class ObjectTypeRequestHandler(BaseRESTRequestHandler):
  """Request handler for object type requests."""

  # conscious change in argument count - pylint:disable-msg=W0221
  def get(self, fullname):
    """Return object type of the requested name."""
    self.response.out.write(get_object_type(fullname))


def get_handler_mapping(urlprefix):
  """Get mapping of URL prefix to handler."""
  logic.check_type(urlprefix, 'urlprefix', basestring)
  mapping = (('%sobjecttype/(.*)' % urlprefix, ObjectTypeRequestHandler),
             ('%sresults/(.*)' % urlprefix, TestResultRequestHandler),
             ('%smodules/(.*)' % urlprefix, ModuleInfoRequestHandler)
             )
  return mapping
