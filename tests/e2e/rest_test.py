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

"""End-to_end tests for the rest module of aeta."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

# Disable checking; pylint: disable-msg=C0111,W0212,R0904,C0103
# - docstrings
# - access to protected members
# - too many public methods
# - setUp() and tearDown() method names

import os
import unittest

from google.appengine.ext import webapp

from aeta import rest
from tests import utils

utils.TestDataMixin().setup_test_data()
# special environment setup - pylint:disable-msg=F0401
import sample_package


# self.handler has to be initialized by child class -
# pylint:disable-msg=E1101
class HandlerTestBase(unittest.TestCase, utils.HandlerTestMixin):
  """Base class for handler tests.

  When using this base class, set 'self.handler' first. then invoke
  the base setUp method.
  """

  def setUp(self):
    self.request = webapp.Request({})
    self.response = webapp.Response()
    self.handler.initialize(self.request, self.response)

  def check_response_text_not_expected(self, not_expected_output,
                                       expected_code):
    if os.environ.get('APPENGINE_RUNTIME') == 'python27':
      result_out = self.handler.response.body
    else:
      self.handler.response.out.flush()
      self.handler.response.out.seek(0)
      result_out = self.handler.response.out.read()
    self.assertNotEqual(not_expected_output, result_out)
    self.assertEqual(expected_code,
                     self.get_response_code(self.handler.response))


class BaseRESTRequestHandlerTest(HandlerTestBase):
  """Tests for the BaseRequestHandler class."""

  def setUp(self):
    self.handler = rest.BaseRESTRequestHandler()
    HandlerTestBase.setUp(self)

  def test_render_error(self):
    msg = 'a sample message'
    status_code = 403
    self.handler.render_error(msg, status_code)
    self.check_response(self.handler.response, status_code, msg)


class ModuleInfoRequestHandlerTest(HandlerTestBase):
  """Tests for the ModuleInfoRequestHandler class."""

  def setUp(self):
    self.handler = rest.ModuleInfoRequestHandler()
    HandlerTestBase.setUp(self)
    self.orig_getmoduledata = rest.get_module_data
    self.json_string = '["foo", "bar"]'
    self.orig_jsonizemoduleinformation = rest.jsonize_module_information

  def tearDown(self):
    rest.get_module_data = self.orig_getmoduledata
    rest.jsonize_module_information = self.orig_jsonizemoduleinformation

  def test_empty_fullname(self):
    rest.jsonize_module_information = lambda _, __: self.json_string
    self.handler.get('')
    self.check_response(self.handler.response, 200, self.json_string)

  def test_normal_fullname(self):
    rest.get_module_data = lambda _, __: ([], [])
    rest.jsonize_module_information = lambda _, __: self.json_string
    self.handler.get('foo.bar')
    self.check_response(self.handler.response, 200, self.json_string)

  def test_load_error(self):
    fullname = '%s.brokenmodule_test' % sample_package.__name__
    self.handler.get(fullname)
    self.check_response_text_not_expected('', 500)


class TestResultRequestHandlerTest(HandlerTestBase):
  """Tests for the TestResultRequestHandler class."""

  def setUp(self):
    self.handler = rest.TestResultRequestHandler()
    HandlerTestBase.setUp(self)
    self.orig_gettestresult = rest.get_test_result_data
    self.json_string = '"foo"'
    self.orig_converttestresult = rest.convert_test_result_data

  def tearDown(self):
    rest.get_test_result_data = self.orig_gettestresult
    rest.convert_test_result_data = self.orig_converttestresult

  def test_empty_fullname(self):
    rest.get_test_result_data = lambda _, __: [0]
    rest.convert_test_result_data = lambda _: self.json_string
    self.handler.get('')
    self.check_response(self.handler.response, 200,
                        '[' + self.json_string + ']')

  def test_non_existing_name(self):
    self.handler.get('nonexistingname')
    self.check_response_text_not_expected('', 404)


class ObjectTypeRequestHandlerTest(HandlerTestBase):
  """Tests for the ObjectTypeRequestHandler class."""

  def setUp(self):
    self.handler = rest.ObjectTypeRequestHandler()
    HandlerTestBase.setUp(self)
    self.orig_getobjecttype = rest.get_object_type
    self.output = 'foo'
    rest.get_object_type = lambda _: self.output

  def tearDown(self):
    rest.get_object_type = self.orig_getobjecttype

  def test_empty_fullname(self):
    self.handler.get('')
    self.check_response(self.handler.response, 200, self.output)

  def test_fullname(self):
    self.handler.get('tests')
    self.check_response(self.handler.response, 200, self.output)


class get_handler_mappingTest(unittest.TestCase):
  """Tests for the GetHandler function."""

  def setUp(self):
    self.urlprefix = '/tests'

  def test_invalid_input(self):
    self.assertRaises(TypeError, rest.get_handler_mapping, None)
    self.assertRaises(TypeError, rest.get_handler_mapping, 5)

  def test_basic_use(self):
    mapping = rest.get_handler_mapping(self.urlprefix)
    self.assertTrue(hasattr(mapping, '__iter__'))
    self.assertTrue(len(mapping))
    for url_pattern, handler in mapping:
      self.assertTrue(isinstance(url_pattern, str))
      self.assertTrue(url_pattern.startswith(self.urlprefix))
      self.assertTrue(issubclass(handler, webapp.RequestHandler), handler)
