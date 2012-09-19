#!/usr/bin/env python
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



import cookielib
import cgi
import getpass
import inspect
import optparse
import os
import StringIO
import sys
import time
import types
import unittest
import urllib
import urllib2
import urlparse
import warnings

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
           'AuthError'
           'RestApiError',
           'TestError',
           'Authenticator',
           'ClientLoginAuthenticator',
           'AetaCommunicator',
           'create_test_cases',
           'add_test_cases_to_module',
          ]


USAGE = """usage: %prog AETA_URL [TESTNAME]

AETA_URL         URL which is handled by the aeta library.
TESTNAME_PREFIX  Optional prefix of all tests to run, e.g. a package name."""

# To indicate that a test module could not be loaded successfully, we
# create a test which raises TestError when executed. Name of the
# class and the test method are defined here.
MODULE_LOAD_ERROR_CLASS_NAME = 'ModuleLoadTest'
MODULE_LOAD_ERROR_METHOD_NAME = 'testModuleLoadedSuccessfully'

# URL to log in to a Google account.
_CLIENT_LOGIN_URL = 'https://www.google.com/accounts/ClientLogin'
# The "source" for ClientLogin is a string identifying the application.
_CLIENT_LOGIN_SOURCE = 'Google-aeta-1.0'
# This allows both Google accounts and other accounts hosted on Google.
_CLIENT_LOGIN_ACCOUNT_TYPE = 'HOSTED_OR_GOOGLE'
# Path on the app server to log in (using a token from ClientLogin).
_APPSERVER_LOGIN_PATH = '/_ah/login'
# Where to store authentication cookies.
_DEFAULT_COOKIE_FILE_PATH = '~/.aeta_cookies'

# Path in REST interface to start a test batch.
_REST_START_BATCH_PATH = 'start_batch'
# Path in REST interface to get batch information.
_REST_BATCH_INFO_PATH = 'batch_info'
# Path in REST interface to poll for test results.
_REST_BATCH_RESULTS_PATH = 'batch_results'

# How long to wait between polling REST calls in seconds.  The actual wait time
# will be incremented by this number each call.
_POLL_BATCH_WAIT_SECS_INC = 0.5


# Copied from py so that local_client.py is standalone.
def check_type(obj, name, typ):
  """Check the type of an object and raise an error if it does not match.

  Args:
    obj: The object to check.
    name: Name of the object shown in a possible error message.
    typ: The expected type of obj.

  Raises:
    TypeError: if obj does not match type_.
  """
  if not isinstance(obj, typ):
    raise TypeError('"%s" (%r) must be a %s, not a %s.' %
                    (name, obj, typ, type(obj)))


class Error(Exception):
  """Base aeta local_client error type."""


class RestApiError(Error):
  """Raised when using the REST API caused an error."""


class AuthError(Error):
  """Raised when authentication failed."""


class TestError(Error):
  """Raised by tests which raised an error."""


class Authenticator(object):
  """A generic authentication interface.

  Attributes:
    is_logged_in: Has the user already logged in?
  """

  def __init__(self):
    self.is_logged_in = False

  def clear_auth(self):
    """Clears authentication information."""
    raise NotImplementedError('clear_auth')

  def get_auth(self):
    """Gets and stores authentication information.

    If the authentication is correct, future requests will not cause
    authentication errors.
    """
    raise NotImplementedError('get_auth')

  def urlopen(self, url, data=None):
    """Opens a given URL using currently stored authentication information.

    Args:
      url: The URL to open.
      data: The POST payload, or None if this should be a GET.

    Returns:
      A file-like object like that returned by urllib2.urlopen().

    Raises:
      urllib2.HTTPError: If an HTTP error occurs, authentication-related or
          not.
    """
    raise NotImplementedError('urlopen')

  def get_url_content(self, url, data=None):
    """Gets the contents of a URL.

    This method will authenticate the user if necessary.

    Args:
      url: The URL to get the content of.
      data: The POST payload, or None if this should be a GET.

    Returns:
      The content of the URL as a string.

    Raises:
      AuthError: If there is a problem with authentication.
      urllib2.HTTPError: If there is some HTTP error not related to
          authentication.
    """
    response = ''
    need_auth = False
    try:
      opened = self.urlopen(url, data)
      response = opened.read()
    except urllib2.HTTPError, err:
      # HTTPError also has geturl() and info() methods, like the return value
      # of urlopen().
      opened = err
      if err.code in [401, 403]:
        need_auth = True
      else:
        raise
    # Check for redirect to login page.
    if need_auth or opened.geturl() != url:
      if self.is_logged_in:
        # User logged in successfully but does not have permission to access
        # tests.
        # We want to re-prompt the user if they run this program again, so
        # clear authentication cookies.
        self.clear_auth()
        raise AuthError('Your account %s does not have permission to access '
                        'aeta tests.  Only admins can access them. ' %
                        self.email)
      self.get_auth()
      self.is_logged_in = True
      return self.get_url_content(url, data)
    return response


class ClientLoginAuth(Authenticator):
  """An authenticator using Google's deprecated ClientLogin interface.

  Attributes:
    email: The email of the current user, or None if it is not known.
    passin: Should the password be entered in stdin?
    save_auth: Should authentication cookies be stored?
    _login_url: The appserver login path (generally http://<app>/_ah/login)
    _cookie_jar: The cookielib.CookieJar used to store authentication cookies.
    _opener: The urllib2 url _opener to use to open URLs with authentication.
  """

  def __init__(self, aeta_url, email=None, passin=False, save_auth=True):
    super(ClientLoginAuth, self).__init__()
    check_type(aeta_url, 'aeta_url', basestring)
    check_type(email, 'email', (types.NoneType, basestring))
    check_type(passin, 'passin', bool)
    check_type(save_auth, 'save_auth', bool)
    self.email = email
    self.passin = passin
    self.save_auth = save_auth
    parsed = urlparse.urlparse(aeta_url)
    self._login_url = urlparse.urlunparse((parsed.scheme, parsed.netloc,
                                          _APPSERVER_LOGIN_PATH, '', '', ''))
    self._cookie_jar = cookielib.LWPCookieJar(
        os.path.expanduser(_DEFAULT_COOKIE_FILE_PATH))
    self._opener = urllib2.build_opener(
        urllib2.HTTPCookieProcessor(self._cookie_jar))
    if self.save_auth and not self.email:
      self._load_auth()
    else:
      self.clear_auth()

  def _load_auth(self):
    """Loads cookies from the cookie file and initializes them properly."""
    try:
      if os.path.exists(self._cookie_jar.filename):
        self._cookie_jar.load()
        print 'Loaded cookies from %s.' % self._cookie_jar.filename
      else:
        # Create file with read/write permission only for the owner.
        os.close(os.open(self._cookie_jar.filename, os.O_CREAT, 0600))
    except IOError, e:
      warnings.warn('Could not load cookies from %s: %s' %
                    (self._cookie_jar.filename, e))

  def clear_auth(self):
    """Clears the cookies both in memory and on disk."""
    self._cookie_jar.clear()
    if os.path.exists(self._cookie_jar.filename):
      self._cookie_jar.save()

  def urlopen(self, url, data=None):
    return self._opener.open(url, data)

  def _get_credentials(self):
    """Gets the username and password used for authentication.

    Returns:
      A (username, password) tuple.
    """
    print 'Log in to your Google account to access aeta tests.'
    if not self.email:
      self.email = raw_input('Email: ')
    prompt = 'Password for %s: ' % self.email
    if self.passin:
      password = raw_input(prompt)
    else:
      password = getpass.getpass(prompt)
    if self.save_auth:
      print ("Authentication cookies will be stored in %s so you won't have "
             "to enter them again.  Use the --no_save_auth option to disable "
             "this behavior." % self._cookie_jar.filename)
    return (self.email, password)

  def _client_login_error(self, err):
    """Raises an appropriate error when ClientLogin fails.

    Args:
      err: A urllib2.HTTPError obtained from ClientLogin.

    Raises:
      AuthError: Invalid authentication.
    """
    body = err.read()
    if err.code == 403:
      err_dict = dict(line.split('=') for line in body.split('\n') if line)
      reason = err_dict['Error']
      info = err_dict.get('Info')
      # Error messages copied from google_appengine/tools/appengine_rpc.py
      if reason == 'BadAuthentication':
        if info == 'InvalidSecondFactor':
          msg = ('Use an application-specific password instead of your '
                 'regular account password.')
        else:
          msg = 'Invalid username or password.'
      elif reason == 'CaptchaRequired':
        msg = ('Please go to\n'
               'https://www.google.com/accounts/DisplayUnlockCaptcha\n'
               'and verify you are a human.  Then try again.')
      else:
        msg = 'Authentication error: %s' % reason
    else:
      msg = 'Error when authenticating: %s"""%s""' % (os.linesep, body)
    raise AuthError(msg)

  def get_auth(self):
    """Gets authentication so future requests will succeed.

    This will prompt the user for login information if necessary.

    Raises:
      AuthError: Invalid authentication.
    """
    # First, hit ClientLogin to get a Google auth token.
    data = {
      'service': 'ah',
      'source': _CLIENT_LOGIN_SOURCE,
      'accountType': _CLIENT_LOGIN_ACCOUNT_TYPE
    }
    data['Email'], data['Passwd'] = self._get_credentials()
    try:
      opened = self.urlopen(_CLIENT_LOGIN_URL, urllib.urlencode(data))
      resp = opened.read()
    except urllib2.HTTPError, err:
      self._client_login_error(err)
    resp_dict = dict(line.split('=') for line in resp.split('\n') if line)
    # Next, use this auth token to log in to the app server.
    args = {'auth': resp_dict['Auth']}
    # /_ah/login will give us a cookie which is automatically used for future
    # requests.
    login = '%s?%s' % (self._login_url, urllib.urlencode(args))
    self.urlopen(login).close()
    if self.save_auth:
      self._cookie_jar.save()


class AetaCommunicator(object):
  """Class which communicates with the aeta REST interface.

  This class also handles authentication if necessary.

  Attributes:
    authenticator: The Authenticator instance to use.
    aeta_url: The absolute URL to aeta, without the trailing slash.
    rest_path: The absolute URL to aeta's rest handler, with the trailing
        slash.
    """

  def __init__(self, authenticator, aeta_url, rest_path='rest'):
    """Initializer.

    Args:
      authenticator: The Authenticator instance to use.
      aeta_url: URL handled by the aeta library.
      rest_path: Path suffix to aeta_path which answers REST requests.
    """
    check_type(authenticator, 'authenticator', Authenticator)
    check_type(aeta_url, 'aeta_url', basestring)
    check_type(rest_path, 'rest_path', basestring)
    self.authenticator = authenticator
    self.aeta_url = aeta_url.strip('/')
    self.rest_path = '%s/%s/' % (self.aeta_url, rest_path.strip('/'))

  def _get_rest_json_data(self, url_suffix, data=None):
    """Gets the JSON data contained at a URL relative to rest_path.

    Args:
      url_suffix: URL, relative to rest_path, of where to make a request.
      data: If None (the default), this will be a GET.  Otherwise, data should
          be a string, and this will make a POST with data as the payload.

    Returns:
      The JSON object returned by the server.

    Raises:
      AuthError: Invalid authentication.
      RestApiError: An error happened communicating with the server.
    """
    url = self.rest_path + url_suffix
    response = ''
    try:
      response = self.authenticator.get_url_content(url, data)
      return json.loads(response)
    except urllib2.HTTPError, err:
      response = err.read()
      if err.code == 400 or err.code == 404:
        msg = 'No data found.'
      elif err.code == 500:
        msg = ('The server returned a 500 and the following error message '
               'while accessing "%s". Please check the server logs for '
               'more details. Error message: %s"""%s"""' % (url, os.linesep,
                                                            response))
      else:
        msg = 'A %s error occured while fetching test data:' % err.code
        msg += '%s"""%s"""' % (os.linesep, response)
      raise RestApiError(msg)
    except JSON_DECODE_ERROR:
      msg = 'Could not decode message: %s"""%s"""' % (os.linesep, response)
      raise RestApiError(msg)

  def start_batch(self, testname):
    """Starts a batch with the given name.

    Args:
      testname: The full name of the test to run.

    Returns:
      A JSON dictionary of data about the batch.  See rest.py for details about
          the format.
    """
    url_suffix = '%s/%s' % (_REST_START_BATCH_PATH, testname)
    return self._get_rest_json_data(url_suffix, '')

  def batch_info(self, batch_id):
    """Gets information about a batch.

    Args:
      batch_id: The string id of the batch.

    Returns:
      A JSON dictionary of data about the batch.  See rest.py for details about
          the format.
    """
    url_suffix = '%s/%s' % (_REST_BATCH_INFO_PATH, batch_id)
    return self._get_rest_json_data(url_suffix)

  def batch_results(self, batch_id, start):
    """Gets results for tests that have completed.

    See rest.py for details about usage.

    Args:
      batch_id: The string id of the batch to get tests in.
      start: The minimum integer index to return test results for.

    Returns:
      A JSON list of dictionaries for test results.  See rest.py for details.
    """
    url_suffix = '%s/%s?start=%s' % (_REST_BATCH_RESULTS_PATH, batch_id, start)
    return self._get_rest_json_data(url_suffix)


class _TestResultUpdater(object):
  """Manages the current state of a test batch and returned results."""

  def __init__(self, comm, testname_prefix):
    """Initializes the _TestResultUpdater.

    Args:
      comm: An AetaCommunicator used to make REST calls.
      testname_prefix: The full name of the test object to run tests for.

    Raises:
      TypeError: Wrong input arguments.
    """
    check_type(comm, 'comm', AetaCommunicator)
    check_type(testname_prefix, 'testname_prefix', basestring)
    self.comm = comm
    self.testname_prefix = testname_prefix
    # ID number of the batch that will be created for these tests.
    self.batch_id = None
    # How many test units are part of the batch.
    self.num_units = None
    # A dictionary mapping test unit name to test method name.
    self.test_unit_methods = None
    # A dictionary mapping module name to exception string for loading errors.
    self.load_errors = None
    # A dictionary mapping test method name to test error string for test
    # errors.
    self.test_errors = {}
    # A dictionary mapping test method name to test failure string for test
    # failures.
    self.test_failures = {}
    # A dictionary mapping test method name to printed test output for that
    # method.
    self.test_outputs = {}
    # A set of test method names that have finished, successfully or not.
    self.test_methods_finished = set()
    # The number of test units that have completed and whose results have been
    # received.
    self.num_units_finished = 0

  def _initialize_batch_info(self, batch_info):
    """Initialize this object with batch info from the server.

    Args:
      batch_info: A JSON object from the server representing batch info.
    """
    self.num_units = batch_info['num_units']
    self.test_unit_methods = batch_info['test_unit_methods']
    self.load_errors = dict(batch_info['load_errors'])

  def _update_results(self, results):
    """Updates this object with test result information from the server.

    Args:
      results: A list of JSON objects from the server represeting test results.
    """
    for result in results:
      unit_name = result['fullname']
      self.test_errors.update(result['errors'])
      self.test_failures.update(result['failures'])
      self.load_errors.update(result['load_errors'])
      test_methods = self.test_unit_methods[unit_name]
      # All test methods in this unit are now finished whether or not they
      # passed.
      self.test_methods_finished.update(test_methods)
      if result['output']:
        # Printing test results is a little awkward because we don't know which
        # test method(s) produced which output.  The best we can do is to
        # attach the output from the entire unit to the first method.
        self.test_outputs[test_methods[0]] = result['output']
    self.num_units_finished += len(results)

  def initialize(self):
    """Starts the batch and gets information about it.

    This will take a while because it requires the server to scan for all tests
    in this batch.  This function initializes the attributes num_units,
    test_unit_methods, and load_errors to their correct values.

    This should be called before calling any other methods.
    """
    if self.batch_id is not None: return
    started = self.comm.start_batch(self.testname_prefix)
    if 'batch_id' not in started:
      self._initialize_batch_info(started['batch_info'])
      self._update_results(started['results'])
      return
    self.batch_id = started['batch_id']
    sleep_time = 0
    while True:
      batch_info = self.comm.batch_info(self.batch_id)
      if batch_info: break
      sleep_time += _POLL_BATCH_WAIT_SECS_INC
      time.sleep(sleep_time)
    self._initialize_batch_info(batch_info)

  def poll_results(self):
    """Updates test results by polling the REST server."""
    if self.batch_id is None:
      raise ValueError('Need to call initialize() first')
    results = self.comm.batch_results(self.batch_id, self.num_units_finished)
    self._update_results(results)

  def create_test_method(self, method_name):
    """Gets a test method that gets its result from the server.

    Args:
      method_name: The full name of the test method.

    Returns:
      A test method.  This should be added to the appropriate test case
      subclass.

      It will poll the server until results for this test are available.  If
      the test failed or errored on the server, then this test method will
      replicate this failure.  Otherwise it will do nothing to indicate that
      the test passed.

    Raises:
      TypeError: Wrong input arguments.
    """
    check_type(method_name, 'method_name', basestring)

    def method(test_case_self):
      # Since this method will be added to a TestCase subclass, test_case_self
      # will be the TestCase instance of the test method.
      path = method_name.split('.')
      sleep_time = 0
      while True:
        # Any prefix of the method name could have a load error.
        for i in range(len(path) + 1):
          prefix = '.'.join(path[:i])
          if prefix in self.load_errors:
            raise TestError(self.load_errors[prefix])
        if method_name in self.test_methods_finished:
          if method_name in self.test_outputs:
            print self.test_outputs[method_name]
          if method_name in self.test_errors:
            raise TestError(self.test_errors[method_name])
          if method_name in self.test_failures:
            test_case_self.fail(self.test_failures[method_name])
          break
        sleep_time += _POLL_BATCH_WAIT_SECS_INC
        time.sleep(sleep_time)
        self.poll_results()

    return method


def _create_load_error_test_case(fullname, traceback, base_class):
  """Create a test case for remote module load errors.

  Args:
    fullname: Full name of the module which could not be loaded.
    traceback: Traceback of the load error.
    base_class: Base class of the test case which will be created.

  Returns:
    A test case with a single test method that raises a TestError.

  Raises:
    TypeError: Wrong input arguments.
  """
  check_type(fullname, 'fullname', basestring)
  check_type(traceback, 'traceback', basestring)
  check_type(base_class, 'base_class', type)
  class_name = '%s.%s' % (fullname, MODULE_LOAD_ERROR_CLASS_NAME)
  new_class = type(str(class_name), (base_class,), {})

  # doesn't need a docstring, dude - pylint:disable-msg=C0111,W0613,
  def test_method(self):
    raise TestError(traceback)

  test_method.__name__ = MODULE_LOAD_ERROR_METHOD_NAME
  setattr(new_class, test_method.__name__, test_method)
  return new_class


def _insert_test_method(classes, base_class, fullname, method):
  """Inserts a given test method into the class structure.

  Args:
    classes: A dictionary mapping test class fullname to test class.  If the
        class indicated by the method name does not exist, it will be created
        and classes/methods will be added here.
    base_class: The base class of test classes.  Should be unittest.TestCase or
        something similar.
    fullname: The full name of the test method, specifying where it should be
        inserted.
    method: The actual test method function.

  Raises:
    TypeError: Wrong input arguments.
  """
  check_type(classes, 'classes', dict)
  check_type(base_class, 'base_class', type)
  check_type(fullname, 'fullname', basestring)
  check_type(method, 'method', types.FunctionType)
  fullname = str(fullname)
  path = fullname.split('.')
  class_name = '.'.join(path[:-1])
  method.__name__ = path[-1]
  if class_name not in classes:
    classes[class_name] = type(class_name, (base_class,), {})
  class_ = classes[class_name]
  if hasattr(class_, method.__name__):
    warnings.warn('Warning: duplicate definition of test method %s' % fullname)
  else:
    setattr(class_, method.__name__, method)


def create_test_cases(aeta_url, base_class, testname_prefix='', email=None,
                      passin=False, save_auth=True):
  """Create local test cases for an aeta-enabled application.

  Args:
    aeta_url: URL where an aeta instance is available.
    base_class: Base class for all generated test cases.
    testname_prefix: Optional name prefix for tests to be created.
    email: The email address to use for authentication, or None for the user to
        enter it when necessary.
    passin: Whether to read the password from stdin rather than echo-free
        input.
    save_auth: Whether to store authentication cookies in a file.

  Returns:
    A list of test cases derived from base_class.

  Raises:
    TypeError: Wrong input arguments.
    RestApiError: If prefix does not specify a valid test object or there was
        some other problem communicating with the aeta REST server.
    AuthError: If there was a problem with authentication.
  """
  check_type(aeta_url, 'aeta_url', basestring)
  check_type(base_class, 'base_class', type)
  check_type(testname_prefix, 'testname_prefix', basestring)
  check_type(email, 'email', (types.NoneType, basestring))
  check_type(passin, 'passin', bool)
  check_type(save_auth, 'save_auth', bool)
  authenticator = ClientLoginAuth(aeta_url, email=email, passin=passin,
                                  save_auth=save_auth)
  comm = AetaCommunicator(authenticator, aeta_url)
  updater = _TestResultUpdater(comm, testname_prefix)
  updater.initialize()
  classes = {}
  for (module_name, traceback) in updater.load_errors.items():
    class_ = _create_load_error_test_case(module_name, traceback, base_class)
    classes[class_.__name__] = class_
  for test_methods in updater.test_unit_methods.values():
    for test_method_name in test_methods:
      method = updater.create_test_method(test_method_name)
      _insert_test_method(classes, base_class, str(test_method_name), method)
  return classes.values()


def add_test_cases_to_module(testcases, module):
  """Add test cases to the given module.

  Args:
    testcases: A list of test cases.
    module: The module the test cases should be added to.

  Raises:
    TypeError: Wrong input arguments.
    ValueError: If the module already has an attribute with a name of
                one of the test cases.
  """
  check_type(testcases, 'testcases', list)
  check_type(module, 'module', types.ModuleType)
  for testcase in testcases:
    if hasattr(module, testcase.__name__):
      raise ValueError('Module "%s" already has an attribute called '
                       '"%s"' % (module.__name__, testcase.__name__))
    setattr(module, testcase.__name__, testcase)


def _print_test_output(start_time, suite):
  """Runs tests and prints the output.

  The output's "Ran <num> test(s) in <num>s" line will be corrected to display
  the correct time.

  Args:
    start_time: When the tests were started, as returned by time.time().
    suite: The unittest.TestSuite to run.
  """
  stream = StringIO.StringIO()
  unittest.TextTestRunner(verbosity=2, stream=stream).run(suite)
  time_taken = time.time() - start_time
  # The TextTestRunner will print out a line "Ran <num> test(s) in <num>s".
  # The time is incorrect because it does not include the time spent in
  # _TestResultUpdater.initialize().  Set this time to be time_taken instead.
  head, sep, tail = stream.getvalue().rpartition(' in ')
  time_len = tail.index('s')
  if time_len == -1: time_len = 0
  print '%s%s%.3f%s' % (head, sep, time_taken, tail[time_len:])


def main(aeta_url, testname_prefix='', email=None, passin=False,
         save_auth=True):
  """Main function invoked if module is run from commandline.

  Args:
    aeta_url: URL where an aeta instance is available.
    testname_prefix: Optional name prefix for tests to be created.
    email: The email address to use for authentication, or None for the user to
        enter it when necessary.
    passin: Whether to read the password from stdin rather than echo-free
        input.
    save_auth: Whether to store authentication cookies in a file.
  """
  try:
    start_time = time.time()
    this_module = inspect.getmodule(main)
    testcases = create_test_cases(aeta_url, unittest.TestCase, testname_prefix,
                                  email=email, passin=passin,
                                  save_auth=save_auth)
    add_test_cases_to_module(testcases, this_module)
    suite = unittest.TestLoader().loadTestsFromModule(this_module)
    if not suite.countTestCases():
      error_msg = 'No tests '
      if testname_prefix:
        error_msg += 'with the prefix "%s" ' % testname_prefix
      error_msg += 'found at "%s"' % aeta_url
      print >> sys.stderr, error_msg
      sys.exit(1)
    _print_test_output(start_time, suite)
    for testcase in testcases:
      delattr(this_module, testcase.__name__)
  except AuthError, e:
    print >> sys.stderr, str(e)


if __name__ == '__main__':
  PARSER = optparse.OptionParser(USAGE)
  PARSER.add_option('-e', '--email', action='store', dest='email',
                    default=None,
                    help='The email address to use for authentication.  '
                         'Will prompt if omitted.')
  PARSER.add_option('--passin', action='store_true', dest='passin',
                    default=False, help='Read the login password from stdin.')
  PARSER.add_option('--no_save_auth', action='store_false', dest='save_auth',
                    default=True,
                    help='Do not save authentication cookies to a local file.')
  (OPTIONS, ARGS) = PARSER.parse_args()
  if not ARGS or len(ARGS) > 2:
    print USAGE
    sys.exit(1)
  INPUT_AETA_URL = ARGS[0]
  INPUT_TESTNAME_PREFIX = ''
  if len(ARGS) == 2:
    INPUT_TESTNAME_PREFIX = ARGS[1]
  main(INPUT_AETA_URL, INPUT_TESTNAME_PREFIX, email=OPTIONS.email,
       passin=OPTIONS.passin, save_auth=OPTIONS.save_auth)
