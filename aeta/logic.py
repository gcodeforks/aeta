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

"""Core logic of aeta.

This module contains all code to load and invoke the tests.

aeta is build around the idea of being able to find and run tests at a
user-defined granularity.

Currently, this module is able to handle the following types of
objects:

- packages containing test cases
- modules containing test cases
- test case classes
- methods of test case classes.

This allows users to invoke tests at different levels of granularity,
e.g., running all tests from a certain package or only a particular
method of a test case.

Objects are addressed by their full name. For packages, this name is
the the name of the package, e.g., my.package. For modules this name
is the name of the module, e.g., my.package.module. For classes this
name is the module name plus the class name
my.package.module.class. Finally, for methods the fullname consists of
the full class name plus the name of the method, e.g.,
my.package.module.class.method.
"""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

import inspect
import logging
import os
import re
import StringIO
import sys
import traceback
import types
import unittest

from aeta import models


__all__ = ['get_abs_path_from_package_name',
           'get_root_relative_path',
           'is_module',
           'load_module_from_module_name',
           'load_modules',
           'get_requested_object',
           'extract_testcase_and_test_method_names',
           'create_module_data',
           'run_test',
           'load_and_run_tests']


def check_type(obj, name, type_):
  """Check the type of an object and raise an error if it does not match.

  If you do not set type_name, type_.__name__ will be used in the
  error message.

  Args:
    obj: The object to check.
    name: Name of the object shown in a possible error message.
    type_: The expected type of obj.

  Raises:
    TypeError: if obj does not match type_.
  """
  if not isinstance(obj, type_):
    if type_ == str:
      type_name = 'string'
    elif type == types.ModuleType:
      type_name = 'module'
    else:
      type_name = type_.__name__
    raise TypeError('"%s" must be a %s, not a %s.' %
                    (name, type_name, type(obj)))


def get_abs_path_from_package_name(packagename):
  """Get absolute file path of the package.

  In order to retrieve the path, the package module will be imported.

  Args:
    packagename: The full package name, e.g., package.subpackage.

  Returns:
    An absolute path or None if path does not exist.

  Raises:
    TypeError: Wrong input arguments.
  """
  check_type(packagename, 'packagename', str)
  errors = []
  mod = load_module_from_module_name(packagename, errors, reload_mod=False)
  if not mod:
    return None
  filename = inspect.getfile(mod)
  if filename.endswith('__init__.py'):
    return filename[:-len('__init__.py')]
  elif filename.endswith('__init__.pyc'):
    return filename[:-len('__init__.pyc')]
  else:
    return None


def get_root_relative_path(path, root):
  """Get the root-relative URL path.

  Example:
    (path='/home/user/app/dir/templates/tests.py',
     root='/home/user/app/dir') -> 'templates/tests.py'

  Args:
    path: An absolute path of a file or directory.
    root: The root directory which equals the websites root path.

  Returns:
    A string representing the root-relative URL path or None if path is not
    relative to root.

  Raises:
    TypeError: Wrong input arguments.
  """
  check_type(path, 'path', str)
  check_type(root, 'root', str)
  if not root or not os.path.isdir(root):
    return None
  path_parts = path.split(os.sep)
  root_parts = root.split(os.sep)
  if not root_parts[-1]:
    del root_parts[-1]
  if root_parts != path_parts[:len(root_parts)]:
    return None
  return '/'.join(path_parts[len(root_parts):])


def is_module(modulename):
  """Returns True if the object identified by modulename is an existing module.

  Note that this function is based on the import of the given module.

  Args:
    modulename: The name of the module, e.g., package.subpackage.module.

  Returns:
    True, if the such a module exists, False otherwise.

  Raises:
    TypeError: Wrong input arguments.
  """
  check_type(modulename, 'modulename', str)
  errors = []
  mod = load_module_from_module_name(modulename, errors, reload_mod=False)
  return bool(mod)


def load_module_from_module_name(fullname, errors_out, reload_mod=True):
  """Load a module.

  Errors which occurred during the import process are appended to
  errors_out. An error is appended as (fullname, error_traceback)
  tuple.

  Args:
    fullname: The full module name, e.g., package.subpackage.module.
    errors_out: A list to which import error tracebacks are appended.
    reload_mod: Try to remove module before reloading it.

  Returns:
    The loaded module or None if the module could not be imported.

  Raises:
    TypeError: Wrong input arguments.
  """
  check_type(fullname, 'fullname', str)
  check_type(errors_out, 'errors_out', list)
  check_type(reload_mod, 'reload_mod', bool)
  module = None
  try:
    loaded_by_import = False
    if fullname not in sys.modules:
      __import__(fullname)
      loaded_by_import = True
    module = sys.modules[fullname]
    if reload_mod and not loaded_by_import:
      module = reload(module)
  #pylint: disable-msg=W0703
  except Exception:
    # For example, NotImplementedError is raised when a module uses
    # functionality which is not allowed in AppEngine, e.g., socket
    # usage.
    errors_out.append((fullname, traceback.format_exc()))
  return module

# TODO(schuppe): too many local variables - pylint: disable-msg=R0914,R0912
def load_modules(packagename, errors_out, module_pattern, depth=0):
  """Load all modules which are part of the package and match module_pattern.

  Errors which occured during the import process are appended to
  errors_out. An error is appended as (fullname, error_traceback)
  tuple.

  Since all modules found at the location of package and below are
  considered , a traversal of the entire directory structure is
  needed. This can be an expansive operation if your path will contain
  many subdirectories and/or files.

  You can limit the depth of the traveral with the depth argument. 1
  means only the first level is considered, 2, the first and the
  second level is considered, and so on. A value of 0 indicates that
  the entire directory tree should be traversed.

  Args:
    packagename: The name of the package, e.g., package.subpackage.
    errors_out: A list to which import error tracebacks are appended.
    module_pattern: The pattern of modules to look at.
    depth: Maximum depth of directory traversal.

  Returns:
    A list of all loaded modules.

  Raises:
    TypeError: Wrong input arguments.
    ValueError: If depth is smaller than 0.
  """
  check_type(packagename, 'packagename', str)
  check_type(errors_out, 'errors_out', list)
  check_type(module_pattern, 'module_pattern', str)
  check_type(depth, 'depth', int)
  if depth < 0:
    raise ValueError('"depth" must be at least 0.')
  path = get_abs_path_from_package_name(packagename)
  if not path:
    return []
  path_default_depth = len([x for x in path.split(os.sep) if x])
  res = []
  packagename_split = packagename.split('.')
  path_split = path.split(os.sep)
  for root, _, files in os.walk(path):
    if depth != 0:
      current_depth = len([x for x in root.split(os.sep) if x])
      if current_depth >= path_default_depth + depth:
        continue
    for file_ in files:
      short_modulename, ext = os.path.splitext(file_)
      # Only Python modules should be considered and they should be
      # considered only once. This means we have to ensure to not use
      # source *and* compiled module files of the same module.
      # At first we check if the current file is a sourcefile. If it
      # is, no further checks are needed and we go ahead and use it.
      if ext != '.py':
        if ext != '.pyc':
          # If it is not a source file nor a compiled file, we ignore it.
          continue
        if ext == '.pyc' and os.path.isfile(os.path.join(root, file_[:-1])):
          # If it is a compiled file and there is a source file, too,
          # we ignore this file, because we are using the source file
          # already.
          continue
      # In addition, only modules matching a certain pattern will be
      # loaded.
      if re.match(module_pattern, short_modulename):
        # The module name = packagename + diff between path and root
        # (=subpackage name) + current file's name.
        root_split = root.split(os.sep)
        if root_split == path_split:
          subpackage_split = []
        else:
          subpackage_split = root_split[len(path_split) - 1:]
        module_split = packagename_split + subpackage_split
        modulename = '.'.join(module_split + [short_modulename])
        new_errors_out = []
        module = load_module_from_module_name(modulename, new_errors_out)
        if module is not None:
          res.append(module)
        else:
          errors_out.extend(new_errors_out)
  res.sort(key=lambda x: x.__name__)
  return res


# TODO(schuppe): too many return statements - pylint: disable-msg=R0911
def get_requested_object(fullname):
  """Get the object described with fullname.

  Note that in order to retrieve the requested object, the object
  itself or the the enclosing module has to be loaded.  Currently,
  packages, modules, classes and methods (unbound) defined in classes
  can be retrieved.

  Args:
    fullname: Name of the object, e.g. package.module.class.method.

  Returns:
    Returns the requested object or None if fullname does not match an object.

  Raises:
    TypeError: Wrong input argument.
  """
  check_type(fullname, 'fullname', str)
  if not fullname:
    return None
  # package
  if get_abs_path_from_package_name(fullname):
    module = load_module_from_module_name(fullname, [], reload_mod=True)
    return module
  # module
  if is_module(fullname):
    module = load_module_from_module_name(fullname, [], reload_mod=True)
    return module
  elements = fullname.split('.')
  # test case
  mod_name = '.'.join(elements[:-1])
  cls_name = elements[-1]
  if is_module(mod_name):
    module = load_module_from_module_name(mod_name, [], reload_mod=True)
    cls = getattr(module, cls_name, None)
    if cls and inspect.isclass(cls):
      return cls
  if len(elements) < 2:
    return None
  # test case method
  mod_name = '.'.join(elements[:-2])
  cls_name = elements[-2]
  method_name = elements[-1]
  if is_module(mod_name):
    # No reload necessary, as this has been done for test case.
    module = load_module_from_module_name(mod_name, [], reload_mod=False)
    cls = getattr(module, cls_name, None)
    if cls and inspect.isclass(cls):
      method = getattr(cls, method_name, None)
      if method and inspect.ismethod(method):
        return method
  return None

# long name, but describes it - pylint:disable-msg=C0103
def extract_test_cases_and_method_names(module):
  """Retrieve all TestCases and their test methods from module.

  The returned names are simple names, that is only the last element
  of the full name.

  Args:
    module: The module from which test cases will be extracted.

  Returns:
    A dict of TestCase names as keys and a list of test method names as value.

  Raises:
    TypeError: Wrong input argument.
  """
  check_type(module, 'module', types.ModuleType)
  res = {}
  # unittest.findTestCases returns a suite of suites
  loader = unittest.TestLoader()
  try:
    testsuites = loader.loadTestsFromModule(module)
  # catch everything = pylint:disable-msg=W0703
  except Exception, err:
    logging.error("Unable to load %s: %s", module, str(err))
    testsuites = []
  for testsuite in testsuites:
    for testcase in testsuite:
      name = testcase.__class__.__name__
      if name not in res:
        res[name] = []
      methodname = testcase.id().split('.')[-1]
      res[name].append(methodname)
  return res


def create_module_data(modules, errors_out):
  """Create model.ModuleData objects from modules and errors_out.

  Args:
    modules: A list of modules to construct moduledata objects from.
    errors_out: A list of (fullname, import error traceback) tuples for modules
            which could not be imported.

  Returns:
    A list of model.ModuleData objects.

  Raises:
    TypeError: Wrong input arguments.
  """
  check_type(modules, 'modules', list)
  check_type(errors_out, 'errors_out', list)
  moduledata = []
  for module in modules:
    fullname = module.__name__
    tests = extract_test_cases_and_method_names(module)
    data = models.ModuleData(fullname, tests=tests)
    moduledata.append(data)
  for error in errors_out:
    fullname = error[0]
    data = models.ModuleData(fullname, load_error=True,
                             load_traceback=error[1])
    moduledata.append(data)
  return moduledata


def _run_test_and_capture_output(test):
  """Run a test and capture the entire output.

  By default, the unittest framework only writes test related data to
  the given stream and ignores other output, e.g., from print
  statements. This function wraps the test execution and captures the
  entire output.

  Args:
    test: The test to run (can be a TestSuite or a TestCase).

  Returns:
    A (testresult, output) tuple. 'testresult' is the return value of
    the TestRunner, 'output' the entire output emitted during the test
    run.
  """
  if not isinstance(test, unittest.TestSuite) and \
        not isinstance(test, unittest.TestCase):
    raise TypeError('"test" must be a TestSuite or a TestCase, not a %s.' %
                    type(test))
  # check_type(suite, 'suite', unittest.TestSuite)
  output = StringIO.StringIO()
  original_stdout = sys.stdout
  original_stderr = sys.stderr
  sys.stdout = output
  sys.stderr = output
  # This nested try-except-finally is a concession made to our 2.4
  # pylint checker.
  try:
    try:
      testresult = unittest.TextTestRunner(stream=output,
                                           verbosity=3).run(test)
    except Exception, err:
      raise err
  finally:
    sys.stdout = original_stdout
    sys.stderr = original_stderr
  return testresult, output.getvalue()


def run_test(obj):
  """Run the tests defined in obj.

  obj can be be a module containing unittest.TestCase classes, a
  unittest.TestCase class itself, or an unbound method of such a
  class.

  Args:
    obj: An object containing test definitions.

  Returns:
    A models.TestResultData object or None if no test object could be found.

  Raises:
    TypeError: obj does not match either of the described object types.
  """
  suite = None
  fullname = None
  if inspect.ismodule(obj):
    suite = unittest.findTestCases(obj)
    fullname = obj.__name__
  elif inspect.isclass(obj):
    suite = unittest.makeSuite(obj)
    fullname = obj.__module__ + '.' + obj.__name__
  elif inspect.ismethod(obj):
    # unittest.findTestCases returns a suite of suites, each
    # containing one test method
    testsuites = unittest.makeSuite(obj.im_class)
    for testsuite in testsuites:
      # pylint: disable-msg=W0212
      if testsuite._testMethodName == obj.__name__:
        suite = testsuite
        fullname = '%s.%s.%s' % (obj.__module__, obj.im_class.__name__,
                                 obj.__name__)
        break
  else:
    raise TypeError('The provided object is neither a test case, '
                    'test method, nor module containing either one.')
  if suite is None:
    logging.info('No test found for  "%s"', obj.__name__)
    return None
  testresult, output = _run_test_and_capture_output(suite)
  result = models.TestResultData(testresult, fullname)
  result.output = output
  return result


def load_and_run_tests(fullname, module_pattern):
  """Load and run all tests found at fullname.

  This method returns a list of Test Results object which contain
  the test results or, if the test could not be loaded, describing the
  error when loading the test case.

  Args:
    fullname: Name of an object, e.g. package.subpackage.module
    module_pattern: The pattern of modules to look at.

  Returns:
    A list of models.TestResultData objects describing the outcome of each
    test.

  Raises:
    TypeError: Wrong input arguments.
  """
  check_type(fullname, 'fullname', str)
  testmodules = []
  errors_out = []
  obj = get_requested_object(fullname)
  if inspect.ismodule(obj):
    errors_out = []
    # If it is a package, load all modules found in this package
    path = get_abs_path_from_package_name(fullname)
    if path is not None:
      modules = load_modules(fullname, errors_out, module_pattern)
      testmodules.extend(modules)
    else:
      testmodules.append(obj)
  elif inspect.isclass(obj):
    testmodules.append(obj)
  elif inspect.ismethod(obj):
    testmodules.append(obj)
  # Note that we silently ignore which occured importing or loading
  # the module.
  testresults = []
  for module in testmodules:
    result = run_test(module)
    if result is None:
      continue
    testresults.append(result)
  return testresults
