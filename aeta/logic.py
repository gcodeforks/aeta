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

"""Core logic of aeta.

This module contains all code to load and invoke the tests.

aeta is build around the idea of being able to find and run tests at a
user-defined granularity.

Currently, this module is able to handle the following types of
objects:

- all test packages
- packages containing test cases
- modules containing test cases
- test case classes
- methods of test case classes.

This allows users to invoke tests at different levels of granularity,
e.g., running all tests from a certain package or only a particular
method of a test case.

Test objects are addressed by their full name. To name all the tests in
conf.test_package_modules, the name is ''. For packages, this name is the the
name of the package, e.g., my.package. For modules this name is the name of the
module, e.g., my.package.module. For classes this name is the module name plus
the class name my.package.module.class. Finally, for methods the fullname
consists of the full class name plus the name of the method, e.g.,
my.package.module.class.method.

A test unit is a test object that is a single unit of work within a test
object.  Each test unit will be run in its own task.  For example, by default
if the test object is a package, its units will be the modules within the
package.
"""



import functools
import inspect
import os
import re
import sys
import traceback
import types
import unittest

from aeta import config
from aeta import utils


__all__ = ['get_abs_path_from_package_name',
           'get_root_relative_path',
           'load_module_from_module_name',
           'get_module_names_in_package',
           'get_requested_object',
           'extract_testcase_and_test_method_names',
           'create_module_data',
           'get_test_suite_from_name',
           'get_test_unit_names',
          ]


class TestObject(object):
  """A object representing a collection of tests.

  Attributes:
    fullname: The full name of the test object.
  """

  def __init__(self, fullname):
    """Initializes the object.

    Args:
      fullname: The full name of the test object.
    """
    utils.check_type(fullname, 'fullname', str)
    self.fullname = fullname

  def get_units(self, conf, errors_out=None):
    """Gets all test units in an object.

    Each test unit is a test object that should be run in its own task.  Each
    unit is a test package, module, class, or test.  As many units as possible
    are returned, subject to the following restrictions:
    1.  A module with setUpModule/tearDownModule, or a class with
        setUpClass/tearDownClass, will not be split up.  This avoids
        duplicating work and running things in parallel that are not supposed
        to be run in parallel.  If duplicating the work is acceptable and it's
        important for the module or class to be parallel, then the user should
        put it in setUp rather than setUpModule or setUpClass.
    2.  Multiple test objects of a certain type should only be run in parallel
        if the appropriate parallelize_{modules,classes,methods} is set.  For
        example if parallelize_classes is set to False, then all classes in a
        module must be run in the same test unit.  Due to task queue overhead,
        parallelizing small units can degrade performance.

    Args:
      conf: A Config object to use for determining parallelization.
      errors_out: A list to which import error tracebacks are appended, or None
          to ignore errors.

    Returns:
      A list of TestObject instances for units contained in this object.
    """
    raise NotImplementedError('get_units')

  def get_methods(self, conf, errors_out=None):
    """Gets a list of test methods contained in this object.

    Args:
      conf: The Config that specifies how to load tests.
      errors_out: A list to which import error tracebacks are appended, or None
          to ignore errors.

    Returns:
      A list of Method instances.
    """
    raise NotImplementedError('get_methods')

  def get_suite(self, conf, errors_out=None):
    """Gets a TestSuite containing all tests in this object.

    Args:
      conf: The Config that specifies how to load tests.
      errors_out: A list to which import error tracebacks are appended, or None
          to ignore errors.

    Returns:
      A TestSuite containing all tests in the object.
    """
    methods = self.get_methods(conf, errors_out)
    return unittest.TestSuite([method.get_test_case() for method in methods])


class TestContainer(TestObject):
  """A test object that contains other test objects."""

  def get_children(self, conf, errors_out):
    """Gets a list of test objects contained in this container.

    Args:
      conf: A Config object for determining where tests are.
      errors_out: A list to which import error tracebacks are appended, or None
          to ignore errors.

    Returns:
      A list of TestObject instances contained in this object.
    """
    raise NotImplementedError('get_children')

  def is_parallel(self, conf):
    """Determines whether tests in this object should be parallelized.

    Args:
      conf: A Config object for determining parallelization.

    Returns:
      Whether or not this object should be split into multiple units to be run
          in parallel.
    """
    raise NotImplementedError('is_parallel')

  def get_methods(self, conf, errors_out=None):
    methods = []
    for child in self.get_children(conf, errors_out):
      methods.extend(child.get_methods(conf, errors_out))
    return methods

  def get_units(self, conf, errors_out=None):
    if self.is_parallel(conf):
      units = []
      for child in self.get_children(conf, errors_out):
        units.extend(child.get_units(conf, errors_out))
      return units
    return [self]


class Root(TestContainer):
  """Represents the root (named '').

  It contains all packages in the configured test_package_names.
  """

  def __init__(self):
    super(Root, self).__init__('')

  def is_parallel(self, conf):
    return conf.parallelize_modules

  def get_children(self, conf, errors_out):
    return [get_requested_object(p, conf) for p in conf.test_package_names]


class Package(TestContainer):
  """Represents a package of tests.

  It contains all modules in the package.
  """

  def __init__(self, fullname):
    super(Package, self).__init__(fullname)

  def is_parallel(self, conf):
    return conf.parallelize_modules

  def get_children(self, conf, errors_out):
    modules = get_module_names_in_package(self.fullname,
                                          conf.test_module_pattern)
    children = []
    for module_name in modules:
      module = load_module_from_module_name(
          module_name, errors_out, include_import_error=True,
          include_test_functions=conf.include_test_functions)
      if module:
        children.append(Module(module_name, module))
    return children


class Module(TestContainer):
  """Represents a module containing tests.

  It contains all TestCase subclasses in the package.

  Attributes:
    module: The module this object represents.
  """

  def __init__(self, fullname, module):
    utils.check_type(module, 'module', types.ModuleType)
    super(Module, self).__init__(fullname)
    self.module = module

  def is_parallel(self, conf):
    return conf.parallelize_classes and not (
        hasattr(self.module, 'setUpModule') or
        hasattr(self.module, 'tearDownModule'))

  def get_children(self, conf, errors_out):
    classes = []
    for cls_name in dir(self.module):
      cls = getattr(self.module, cls_name)
      if isinstance(cls, type) and issubclass(cls, unittest.TestCase):
        classes.append(Class('%s.%s' % (self.fullname, cls_name), cls))
    return classes


class Class(TestContainer):
  """Represents a test class (a subclass of TestCase).

  It contains all methods of the class that match the appropriate pattern
  defined by the unittest module (by default, the ones that start with 'test').

  Attributes:
    class_: The TestCase subclass this object represents.
  """

  def __init__(self, fullname, class_):
    utils.check_type(class_, 'class_', type)
    super(Class, self).__init__(fullname)
    self.class_ = class_

  def is_parallel(self, conf):
    if not conf.parallelize_methods:
      return False
    for name in ['setUpClass', 'tearDownClass']:
      # Check if self.class_ overrode the method by comparing its
      # implementation to unittest.TestCase's.
      class_method = getattr(self.class_, name, None)
      class_func = class_method and class_method.im_func
      super_method = getattr(unittest.TestCase, name, None)
      super_func = super_method and super_method.im_func
      if class_func is not super_func:
        return False
    return True

  def get_children(self, conf, errors_out):
    methods = []
    for method_name in unittest.TestLoader().getTestCaseNames(self.class_):
      methods.append(Method('%s.%s' % (self.fullname, method_name),
                            self.class_, method_name))
    return methods


class Method(TestObject):
  """Represents a test method.

  Attributes:
    class_: The TestCase subclass containing this method.
    method_name: The name of the method.
  """

  def __init__(self, fullname, class_, method_name):
    utils.check_type(class_, 'class_', type)
    utils.check_type(method_name, 'method_name', str)
    super(Method, self).__init__(fullname)
    self.class_ = class_
    self.method_name = method_name

  def get_units(self, conf, errors_out=None):
    return [self]

  def get_methods(self, conf, errors_out=None):
    return [self]

  def get_test_case(self):
    """Gets a unittest.TestCase object that will run this method.

    Returns:
      A TestCase for this method.  It will have an extra attribute, 'fullname',
          set to self.fullname.
    """
    case = self.class_(self.method_name)
    case.fullname = self.fullname
    return case


class BadTest(TestObject):
  """Represents a test object that does not exist or could not be loaded.

  Attributes:
    exists: A boolean indicating whether or not the object exists.  The object
        could exist but might not have been loaded successfully.
    load_errors: A list of (fullname, error string) for the errors encountered
        getting this object.
  """

  def __init__(self, fullname, exists, load_errors):
    utils.check_type(exists, 'exists', bool)
    utils.check_type(load_errors, 'load_errors', list)
    if not load_errors:
      raise ValueError('No load errors specified for BadTest')
    super(BadTest, self).__init__(fullname)
    self.exists = exists
    self.load_errors = load_errors

  def get_units(self, conf, errors_out=None):
    if errors_out is not None: errors_out.extend(self.load_errors)
    return []

  def get_methods(self, conf, errors_out=None):
    if errors_out is not None: errors_out.extend(self.load_errors)
    return []


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
  utils.check_type(packagename, 'packagename', str)
  errors = []
  mod = load_module_from_module_name(packagename, errors, reload_mod=False,
                                     include_test_functions=False)
  # The __init__ module is not a package, but anything else whose file's name
  # ends with __init__.py(c) is.
  if not mod or mod.__name__.split('.')[-1] == '__init__':
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
  utils.check_type(path, 'path', str)
  utils.check_type(root, 'root', str)
  if not root or not os.path.isdir(root):
    return None
  path_parts = path.split(os.sep)
  root_parts = root.split(os.sep)
  if not root_parts[-1]:
    del root_parts[-1]
  if root_parts != path_parts[:len(root_parts)]:
    return None
  return '/'.join(path_parts[len(root_parts):])


def _wrap_function(func):
  """Wraps a function with a wrapper that discards a single arguments.

  This is to allow functions to be used as methods similarly to using
  staticmethod, but still contain a reference to the class and return True for
  inspect.ismethod calls.

  Args:
    func: A function that takes no arguments to wrap.

  Returns:
    A one argument function that wraps the provided function.
  """
  return functools.wraps(func)(lambda self: func())


def wrap_test_functions(module):
  """Wraps test functions with a new TestCase subclass.

  Args:
    module: A module to search for test functions to wrap.
  """
  _, _, submodule_name = module.__name__.rpartition('.')
  test_case_name = ''.join(
      s[:1].upper() + s[1:] for s in submodule_name.split('_'))
  test_case_name += 'WrappedTestFunctions'  # Prevent name collision.
  if hasattr(module, test_case_name):
    return
  test_functions = {}
  for name, obj in module.__dict__.items():
    if inspect.isfunction(obj) and name.startswith('test'):
      test_functions[name] = _wrap_function(obj)
  if test_functions:
    test_case = type(test_case_name, (unittest.TestCase,), test_functions)
    test_case.__module__ = module.__name__
    module.__dict__[test_case_name] = test_case


def load_module_from_module_name(fullname, errors_out=None, reload_mod=False,
                                 include_import_error=False,
                                 include_test_functions=True):
  """Load a module.

  Errors which occurred while importing the module are appended to errors_out.
  An error is appended as (fullname, error_traceback) tuple.

  Args:
    fullname: The full module name, e.g., package.subpackage.module.
    errors_out: A list to which import error tracebacks are appended, or None
        to ignore errors.
    reload_mod: Try to remove module before reloading it.
    include_import_error: Whether to include an error tuple in case the module
        does not exist.
    include_test_functions:  Whether to wrap test functions into a test case
        class.  Note that if this is False and the module has already been
        imported with include_test_functions=True, then the module will still
        have the wrapped test functions from before.

  Returns:
    The loaded module or None if the module could not be imported.

  Raises:
    TypeError: Wrong input arguments.
  """
  utils.check_type(fullname, 'fullname', str)
  utils.check_type(errors_out, 'errors_out', (types.NoneType, list))
  utils.check_type(reload_mod, 'reload_mod', bool)
  utils.check_type(include_import_error, 'include_import_error', bool)
  utils.check_type(include_test_functions, 'include_test_functions', bool)
  module = None
  try:
    loaded_by_import = False
    if fullname not in sys.modules:
      __import__(fullname)
      loaded_by_import = True
    module = sys.modules[fullname]
    if reload_mod and not loaded_by_import:
      module = reload(module)
    if include_test_functions:
      wrap_test_functions(module)
  # pylint: disable-msg=W0703
  except:
    if errors_out is not None:
      if include_import_error:
        errors_out.append((fullname, traceback.format_exc()))
      else:
        # The error should only be noted if the exception was raised from
        # within the imported module, rather than being raised because the
        # module did not exist.  To check this, walk the traceback stack and
        # look for a module with __name__ == fullname (or None due to the
        # broken module being cleared).
        tb = sys.exc_info()[2]
        while tb:
          if tb.tb_frame.f_globals['__name__'] in [None, fullname]:
            errors_out.append((fullname, traceback.format_exc()))
            break
          tb = tb.tb_next
  return module


# TODO(user): too many local variables - pylint: disable-msg=R0914,R0912
def get_module_names_in_package(packagename, module_pattern, depth=0):
  """Get names of all modules in the package that match module_pattern.

  Since all modules found at the location of package and below are
  considered, a traversal of the entire directory structure is
  needed. This can be an expansive operation if your path will contain
  many subdirectories and/or files.

  You can limit the depth of the traveral with the depth argument. 1
  means only the first level is considered, 2, the first and the
  second level is considered, and so on. A value of 0 indicates that
  the entire directory tree should be traversed.

  Args:
    packagename: The name of the package, e.g., package.subpackage.
    module_pattern: The pattern of modules to look at.
    depth: Maximum depth of directory traversal.

  Returns:
    A list of full names of modules in this package that match the pattern.

  Raises:
    TypeError: Wrong input arguments.
    ValueError: If depth is smaller than 0.
  """
  utils.check_type(packagename, 'packagename', str)
  utils.check_type(module_pattern, 'module_pattern', str)
  utils.check_type(depth, 'depth', int)
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
        res.append(modulename)
  res.sort()
  return res


def _is_prefix(prefix, name):
  """Determines whether one fullname is a prefix of another.

  Args:
    prefix: The fullname that might be a prefix.
    name: The entire fullname.

  Returns:
    A boolean indicating whether or not the first fullname is a prefix of the
        second.
  """
  prefix_parts = prefix.split('.') if prefix else []
  name_parts = name.split('.') if name else []
  return name_parts[:len(prefix_parts)] == prefix_parts


def _is_in_test_package(fullname, conf):
  """Determines whether the given fullname is in a configured test package.

  Args:
    fullname: The name of a test object.
    conf: The configuration to use.

  Returns:
    A boolean indicating whether or not the fullname is valid (in one of the
    configured test packages).
  """
  return any(_is_prefix(p, fullname) for p in conf.test_package_names)


def get_requested_object(fullname, conf):
  """Gets the TestObject with the particular name.

  Args:
    fullname: Name of the object, e.g. package.module.class.method.
    conf: The configuration to use.

  Returns:
    A TestObject, which might be BadTest if the object cannot be found or
        loaded correctly.

  Raises:
    TypeError: Wrong input arguments.
  """
  utils.check_type(fullname, 'fullname', str)
  utils.check_type(conf, 'conf', config.Config)
  if not fullname:
    return Root()
  if not _is_in_test_package(fullname, conf):
    msg = ('Test object %s is not contained in one of the configured '
           'test_package_names in aeta.yaml.' % fullname)
    return BadTest(fullname, False, [(fullname, msg)])
  errors_out = []
  # package or module
  module = load_module_from_module_name(
      fullname, errors_out, include_import_error=False,
      include_test_functions=conf.include_test_functions)
  if errors_out:
    return BadTest(fullname, True, errors_out)
  if module:
    if get_abs_path_from_package_name(fullname):
      return Package(fullname)
    return Module(fullname, module)
  elements = fullname.split('.')
  # test case class
  module = load_module_from_module_name(
      '.'.join(elements[:-1]), errors_out, include_import_error=False,
      include_test_functions=conf.include_test_functions)
  if errors_out:
    return BadTest(fullname, True, errors_out)
  if module:
    cls = getattr(module, elements[-1], None)
    if cls and inspect.isclass(cls):
      return Class(fullname, cls)
  module = load_module_from_module_name(
      '.'.join(elements[:-2]), errors_out, include_import_error=False,
      include_test_functions=conf.include_test_functions)
  if errors_out:
    return BadTest(fullname, True, errors_out)
  if module:
    cls_name, method_name = elements[-2:]
    cls = getattr(module, cls_name, None)
    if cls and inspect.isclass(cls):
      method = getattr(cls, method_name, None)
      if method and inspect.ismethod(method):
        return Method(fullname, cls, method_name)
  return BadTest(fullname, False,
                 [(fullname, 'No test object %s.' % fullname)])

