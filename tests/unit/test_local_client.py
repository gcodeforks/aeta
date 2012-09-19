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

"""Tests for the local_client module of aeta."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

# Disable checking; pylint: disable-msg=C0111,W0212,R0904,C0103,R0902,R0201
# - docstrings
# - access to protected members
# - too many public methods
# - setUp() and tearDown() method names
# - too many instance attributes
# - method could be a function

import cgi
import cookielib
import os.path
import StringIO
import sys
import time
import types
import unittest
import urllib2

import simplejson as json

from aeta import local_client
from tests import utils


class CreateLoadErrorTestCaseTest(unittest.TestCase):
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


class ClientLoginAuthTest(unittest.TestCase, utils.MockAttributeMixin):
  """Tests for ClientLoginAuth and Authenticator."""

  def setUp(self):
    self.url = 'http://www.example.com'
    self.aeta_url = self.url + '/tests/'
    self.expected_url = self.aeta_url + 'suffix'
    self.expected_post_data = None
    self.http_error_code = None
    self.http_error_message = 'an error message'
    self.http_content = '{"foo": "bar"}'

    # Mapping of email to (password, token).
    self.email_info = {'admin@example.com': ('adminpass', 'admintoken'),
                       'user@example.com': ('userpass', 'usertoken')}
    # Mapping of token to whether they are an admin.
    self.token_info = {'admintoken': True, 'usertoken': False}
    # Is authorization required?
    self.need_auth = False
    # On auth fail, should the server redirect to a login page (rather than
    # return 401/403)?
    self.redirect = True
    # Queue of (email or None, password) for credentials the user will enter.
    self.credential_input = []
    # Is there a stored cookie for someone logged in to the app server?
    self.stored_is_logged_in = False
    # Is this cookie for an admin user?
    self.stored_is_admin = False

    @self.mock(os.path)
    def exists(filename):
      return True

    @self.mock(cookielib)
    class LWPCookieJar(object):
      """Mock jar to save cookies in selfy.stored_* rather than a file."""

      def __init__(self, filename):
        self.filename = filename
        self.is_logged_in = False
        self.is_admin = False

      def load(jar_self):
        jar_self.is_logged_in = self.stored_is_logged_in
        jar_self.is_admin = self.stored_is_admin

      def clear(jar_self):
        jar_self.is_logged_in = False
        jar_self.is_admin = False

      def save(jar_self):
        self.stored_is_logged_in = jar_self.is_logged_in
        self.stored_is_admin = jar_self.is_admin

    @self.mock(local_client.ClientLoginAuth)
    def _get_credentials(auth_self):
      """Mock _get_credentials to use credential_input."""
      in_email, in_pass = self.credential_input.pop(0)
      if auth_self.email:
        self.assertEqual(None, in_email)
      else:
        self.assertNotEqual(None, in_email)
        auth_self.email = in_email
      return (auth_self.email, in_pass)

    class Opened(urllib2.HTTPError):
      """A file-like object suitable for returning from open().

      It also inherits from HTTPError so it can also be raised as an error.
      """

      def __init__(self, content, url, code=None):
        self.content = content
        self.url = url
        self.code = code

      def read(self):
        return self.content

      def close(self):
        pass

      def geturl(self):
        return self.url

    class Opener(object):
      """An opener like the one returned by urllib2.build_opener()."""

      def __init__(self, cookie_jar):
        self.cookie_jar = cookie_jar

      def open(opener_self, url, data=None):
        if url == local_client._CLIENT_LOGIN_URL:
          query = cgi.parse_qs(data)
          email = query['Email'][0]
          if email not in self.email_info:
            raise Opened('Error=BadAuthentication', url, code=403)
          exp_pass, token = self.email_info[email]
          if exp_pass != query['Passwd'][0]:
            raise Opened('Error=BadAuthentication', url, code=403)
          return Opened('Auth=' + token, url)
        elif url.startswith(self.url + local_client._APPSERVER_LOGIN_PATH):
          query = cgi.parse_qs(url[url.find('?') + 1:])
          token = query['auth'][0]
          if token not in self.token_info:
            raise Opened('Bad token', url, code=403)
          opener_self.cookie_jar.is_admin = self.token_info[token]
          opener_self.cookie_jar.is_logged_in = True
          return Opened('', url)
        else:
          self.assertEqual(self.expected_url, url)
          self.assertEqual(self.expected_post_data, data)
          if self.need_auth and not opener_self.cookie_jar.is_admin:
            if self.redirect:
              redirect_url = 'https://accounts.google.com/ServiceLogin?a'
              return Opened('login page', redirect_url)
            if opener_self.cookie_jar.is_logged_in:
              raise Opened('forbidden', url, code=403)
            raise Opened('need login', url, code=401)
          if self.http_error_code:
            raise Opened(self.http_error_message, url,
                         code=self.http_error_code)
          return Opened(self.http_content, url)

    @self.mock(urllib2)
    def build_opener(processor):
      self.assertTrue(processor.cookiejar)
      return Opener(processor.cookiejar)

  def tearDown(self):
    self.tear_down_attributes()

  def check_auth(self, test):
    """Runs an authentication test with various settings.

    Args:
      test: A function to run with different settings.
    """
    self.need_auth = True
    for self.redirect in [False, True]:
      self.stored_is_logged_in = False
      self.stored_is_admin = False
      test()

  def check_auth_success(self, auth=None, save_auth=True):
    """Gets and checks REST data, requiring authentication to succeed."""
    if auth is None:
      auth = local_client.ClientLoginAuth(self.aeta_url)
    test_data = auth.get_url_content(self.expected_url)
    self.assertEqual(self.http_content, test_data)
    self.assertEqual(save_auth, self.stored_is_logged_in)
    self.assertEqual(save_auth, self.stored_is_admin)

  def check_auth_fail(self, auth=None):
    """Tries to get REST data, requiring authentication to fail."""
    if auth is None:
      auth = local_client.ClientLoginAuth(self.aeta_url)
    self.assertRaises(local_client.AuthError, auth.get_url_content,
                      self.expected_url)

  def test_auth_success(self):
    def test():
      self.credential_input = [('admin@example.com', 'adminpass')]
      self.check_auth_success()
    self.check_auth(test)

  def test_bad_password(self):
    def test():
      self.credential_input = [('admin@example.com', 'badpass')]
      self.check_auth_fail()
    self.check_auth(test)

  def test_non_admin(self):
    def test():
      self.credential_input = [('user@example.com', 'userpass')]
      self.check_auth_fail()
    self.check_auth(test)

  def test_stored_admin(self):
    def test():
      self.stored_is_logged_in = True
      self.stored_is_admin = True
      self.check_auth_success()
    self.check_auth(test)

  def test_stored_non_admin(self):
    def test():
      self.stored_is_logged_in = True
      self.stored_is_admin = False
      self.credential_input = [('admin@example.com', 'adminpass')]
      self.check_auth_success()
    self.check_auth(test)

  def test_set_email(self):
    def test():
      self.credential_input = [(None, 'adminpass')]
      comm = local_client.ClientLoginAuth(self.aeta_url,
                                          email='admin@example.com')
      self.check_auth_success(comm)
    self.check_auth(test)

  def test_set_email_non_admin(self):
    def test():
      self.stored_is_logged_in = True
      self.stored_is_admin = True
      self.credential_input = [(None, 'userpass')]
      comm = local_client.ClientLoginAuth(self.aeta_url,
                                          email='user@example.com')
      self.check_auth_fail(comm)
      self.assertFalse(self.stored_is_logged_in)
      self.assertFalse(self.stored_is_admin)
    self.check_auth(test)

  def test_no_cookies_clear(self):
    def test():
      self.stored_is_logged_in = True
      self.stored_is_admin = True
      self.credential_input = [('admin@example.com', 'adminpass')]
      comm = local_client.ClientLoginAuth(self.aeta_url, save_auth=False)
      self.check_auth_success(comm, save_auth=False)
    self.check_auth(test)


class MockAuthenticator(local_client.Authenticator):
  """Mock Authenticator to make get_url_content return specified things.

  Attributes:
    test: The TestCase instance to use to report errors.
    expected_url: The url that should be passed to get_url_content.
    expected_data: The POST data that should be passed to get_url_content.
    error_code: Which HTTP error to raise, or None to raise no error.
    error_message: If there is an error, return this as the content.
    url_content: If there is no error, return this as the content.
  """

  def __init__(self, test):
    self.test = test
    self.expected_url = None
    self.expected_data = None
    self.error_code = None
    self.error_message = 'an error message'
    self.url_content = 'content'

  def get_url_content(self, url, data=None):
    self.test.assertEqual(self.expected_url, url)
    self.test.assertEqual(self.expected_data, data)
    if not self.error_code:
      return self.url_content
    error = urllib2.HTTPError(url, self.error_code, '', None, None)
    error.read = lambda: self.error_message
    raise error


class AetaCommunicatorTest(unittest.TestCase, utils.MockAttributeMixin):
  """Tests for AetaCommunicator."""

  def setUp(self):
    self.url = 'http://www.example.com'
    self.authenticator = MockAuthenticator(self)
    self.comm = local_client.AetaCommunicator(self.authenticator, self.url)
    self.authenticator.expected_url = self.comm.rest_path + 'suffix'

  def tearDown(self):
    self.tear_down_attributes()

  def test_init(self):
    local_client.AetaCommunicator(self.authenticator, 'some random string')
    local_client.AetaCommunicator(self.authenticator, 'some random string',
                                  rest_path='another string')

  def test_get_json_data_without_post(self):
    url_content = self.authenticator.url_content = '{"foo": "bar"}'
    test_data = self.comm._get_rest_json_data('suffix')
    self.assertEqual(json.loads(url_content), test_data)

  def test_get_json_data_with_post(self):
    expected_data = self.authenticator.expected_data = {'a': 'b'}
    url_content = self.authenticator.url_content = '{"foo": "bar"}'
    test_data = self.comm._get_rest_json_data('suffix', expected_data)
    self.assertEqual(json.loads(url_content), test_data)

  def test_get_json_data_with_http_error(self):
    for self.authenticator.error_code in [400, 404, 500, 501, 502, 503]:
      self.assertRaises(local_client.RestApiError,
                        self.comm._get_rest_json_data, 'suffix')

  def test_get_json_data_with_http_error_500(self):
    self.authenticator.error_code = 500
    error_message = self.authenticator.error_message = 'server error message'
    error = None
    try:
      self.comm._get_rest_json_data('suffix')
    except local_client.RestApiError, e:
      error = e
    self.assertTrue(self.url in str(error))
    self.assertTrue(error_message in str(error))

  def test_bad_json_from_server(self):
    self.authenticator.url_content = 'bad json'
    self.assertRaises(local_client.RestApiError, self.comm._get_rest_json_data,
                      'suffix')


class TestResultUpdaterTest(unittest.TestCase, utils.MockAttributeMixin):
  """Tests for the _TestResultUpdater class."""

  def setUp(self):
    self.communicator = local_client.AetaCommunicator(
        local_client.Authenticator(), 'www.example.com')
    self.testname = 'tests'
    self.updater = local_client._TestResultUpdater(self.communicator,
                                                   self.testname)
    self.batch_info = None
    self.future_batch_info = {
        'num_units': 3,
        'test_unit_methods': {
            'tests.Case1': ['tests.Case1.test1', 'tests.Case1.test2'],
            'tests.Case2': ['tests.Case2.test1', 'tests.Case2.test2'],
            'tests.badmodule': ['tests.badmodule.Case.test_method']
        },
        'load_errors': [('tests.module', 'ImportError')]
    }
    self.started_batch = False
    self.batch_id = 1234
    self.sleep_count = 0
    self.finished_results = [
        {'load_errors': [],
         'errors': [('tests.Case1.test1', 'TypeError')],
         'failures': [('tests.Case1.test2', 'Things are not as expected')],
         'fullname': 'tests.Case1',
         'output': 'some stuff happened'},
        None,
        {'load_errors': [('tests.badmodule', 'ImportError')],
         'errors': [],
         'failures': [],
         'fullname': 'tests.badmodule',
         'output': 'some more stuff happened'}
    ]

    @self.mock(local_client.AetaCommunicator)
    def start_batch(comm_self, testname):
      self.assertEqual(self.testname, testname)
      self.assertFalse(self.started_batch)
      self.started_batch = True
      return {'batch_id': self.batch_id}

    @self.mock(local_client.AetaCommunicator)
    def batch_info(comm_self, batch_id):
      self.assertEqual(self.batch_id, batch_id)
      return self.batch_info

    @self.mock(time)
    def sleep(secs):
      self.batch_info = self.future_batch_info
      if self.sleep_count >= 2:
        self.finished_results[1] = {'load_errors': [], 'errors': [],
                                    'failures': [], 'fullname': 'tests.Case2',
                                    'output': 'everything is good'}
      if self.sleep_count >= 3:
        self.fail('Slept more than necessary')
      self.sleep_count += 1

    @self.mock(local_client.AetaCommunicator)
    def batch_results(comm_self, batch_id, start):
      self.assertEqual(self.batch_id, batch_id)
      results = []
      for i in range(start, len(self.finished_results)):
        if not self.finished_results[i]: break
        results.append(self.finished_results[i])
      return results

    # We need fake test cases to pass into generated test methods as self.
    class Case(unittest.TestCase):

      def test(self):
        pass

    self.test_case = Case('test')

  def tearDown(self):
    self.tear_down_attributes()

  def test_initialize(self):
    self.updater.initialize()
    self.assertEqual(self.future_batch_info['num_units'],
                     self.updater.num_units)
    self.assertEqual(self.future_batch_info['test_unit_methods'],
                     self.updater.test_unit_methods)
    self.assertEqual(dict(self.future_batch_info['load_errors']),
                     self.updater.load_errors)

  def test_immediate(self):
    self.finished_results[1] = {
        'load_errors': [], 'errors': [], 'failures': [],
        'fullname': 'tests.Case2', 'output': 'everything is good'}

    @self.mock(local_client.AetaCommunicator)
    def start_batch(comm_self, testname):
      self.assertEqual(self.testname, testname)
      self.assertFalse(self.started_batch)
      self.started_batch = True
      return {'batch_info': self.future_batch_info,
              'results': self.finished_results}

    self.updater.initialize()
    self.assertEqual(3, self.updater.num_units_finished)
    self.assertEqual(5, len(self.updater.test_methods_finished))
    self.assertEqual({'tests.Case1.test1': 'TypeError'},
                     self.updater.test_errors)
    self.assertEqual({'tests.Case1.test2': 'Things are not as expected'},
                     self.updater.test_failures)
    self.assertEqual(2, len(self.updater.load_errors))
    self.assertEqual('some stuff happened',
                     self.updater.test_outputs['tests.Case1.test1'])

  def test_poll_results(self):
    self.updater.initialize()
    self.updater.poll_results()
    # Should have updated using first test result.
    self.assertEqual({'tests.Case1.test1': 'TypeError'},
                     self.updater.test_errors)
    self.assertEqual({'tests.Case1.test2': 'Things are not as expected'},
                     self.updater.test_failures)
    self.assertEqual(set(['tests.Case1.test1', 'tests.Case1.test2']),
                     self.updater.test_methods_finished)
    self.assertEqual(1, self.updater.num_units_finished)
    self.assertEqual('some stuff happened',
                     self.updater.test_outputs['tests.Case1.test1'])

  def test_create_test_method_error(self):
    self.updater.initialize()
    method = self.updater.create_test_method('tests.Case1.test1')
    self.assertRaises(local_client.TestError, method, self.test_case)

  def test_create_test_method_fail(self):
    self.updater.initialize()
    method = self.updater.create_test_method('tests.Case1.test2')
    self.assertRaises(AssertionError, method, self.test_case)

  def test_create_test_method_pass(self):
    self.updater.initialize()
    method = self.updater.create_test_method('tests.Case2.test1')
    # Capture printed output (which should be test output).
    stdout = StringIO.StringIO()
    self.mock(sys, 'stdout')(stdout)
    # Should succeed without exceptions.
    method(self.test_case)
    self.assertTrue('everything is good' in stdout.getvalue())

  def test_create_test_method_load_error(self):
    self.updater.initialize()
    method = self.updater.create_test_method('tests.badmodule.Case3.test1')
    self.assertRaises(local_client.TestError, method, self.test_case)


class InsertTestMethodTest(unittest.TestCase):
  """Tests for _insert_test_method."""

  def setUp(self):
    self.test_method = lambda test_case_self: None

  def test_new_class(self):
    classes = {}
    local_client._insert_test_method(classes, unittest.TestCase,
                                     'module.Class.test_method',
                                     self.test_method)
    cls = classes.get('module.Class', None)
    self.assertTrue(issubclass(cls, unittest.TestCase))
    self.assertEqual('module.Class', cls.__name__)
    method = getattr(cls, 'test_method', None)
    self.assertEqual(self.test_method, method.im_func)
    self.assertEqual('test_method', method.__name__)

  def test_old_class(self):
    class Class(unittest.TestCase):
      def test1(self):
        pass
    classes = {'module.Class': Class}
    local_client._insert_test_method(classes, unittest.TestCase,
                                     'module.Class.test2', self.test_method)
    self.assertEqual(Class, classes.get('module.Class', None))
    method = getattr(Class, 'test2', None)
    self.assertEqual(self.test_method, method.im_func)
    self.assertEqual('test2', method.__name__)

  def test_old_method(self):
    class Class(unittest.TestCase):
      def test_method(self):
        pass
    old_method = Class.test_method
    classes = {'module.Class': Class}
    # Should do nothing, preserving old method.
    local_client._insert_test_method(classes, unittest.TestCase,
                                     'module.Class.test_method',
                                     self.test_method)
    self.assertEqual(old_method, Class.test_method)


class CreateTestCasesTest(unittest.TestCase, utils.MockAttributeMixin):
  """Tests for create_test_cases."""

  def setUp(self):
    self.load_errors = {'tests.badmodule': 'ImportError'}
    self.test_unit_methods = {
        'tests.module.Case1': ['tests.module.Case1.test1',
                               'tests.module.Case1.test2'],
        'tests.module.Case2': ['tests.module.Case2.test_method']
    }

    @self.mock(local_client._TestResultUpdater)
    def initialize(updater_self):
      updater_self.load_errors = self.load_errors
      updater_self.test_unit_methods = self.test_unit_methods

    @self.mock(local_client._TestResultUpdater)
    def create_test_method(updater_self, fullname):
      method = lambda test_case_self: None
      method.fullname = fullname
      return method

  def tearDown(self):
    self.tear_down_attributes()

  def test_create_cases(self):
    classes = local_client.create_test_cases('www.example.com',
                                             unittest.TestCase, 'tests')
    name1 = 'tests.module.Case1'
    name2 = 'tests.module.Case2'
    badname = 'tests.badmodule.' + local_client.MODULE_LOAD_ERROR_CLASS_NAME
    badcase, case1, case2 = sorted(classes, key=lambda c: c.__name__)

    self.assertEqual(name1, case1.__name__)
    self.assertEqual(name1 + '.test1', case1.test1.fullname)
    self.assertEqual(name1 + '.test2', case1.test2.fullname)

    self.assertEqual(name2, case2.__name__)
    self.assertEqual(name2 + '.test_method', case2.test_method.fullname)

    self.assertEqual(badname, badcase.__name__)
    method_name = local_client.MODULE_LOAD_ERROR_METHOD_NAME
    self.assertTrue(hasattr(badcase, method_name))

  def test_no_tests(self):
    self.load_errors = {}
    self.test_unit_methods = {}
    classes = local_client.create_test_cases('www.example.com',
                                             unittest.TestCase, 'tests')
    self.assertEqual([], classes)


class AddTestCasesToModuleTest(unittest.TestCase):
  """Tests for add_test_cases_to_module."""

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
    test_cases = []
    for name in names:
      test_case = type(name, (self.base_class,), {})
      test_cases.append(test_case)
    local_client.add_test_cases_to_module(test_cases, test_mod)
    for i, name in enumerate(names):
      self.assertTrue(hasattr(test_mod, name))
      self.assertEqual(test_cases[i], getattr(test_mod, name))

  def test_attributes_already_exist(self):
    test_mod = types.ModuleType('test_module')
    test_case = type('TestCase', (self.base_class,), {})
    local_client.add_test_cases_to_module([test_case], test_mod)
    self.assertRaises(ValueError, local_client.add_test_cases_to_module,
                      [test_case], test_mod)
