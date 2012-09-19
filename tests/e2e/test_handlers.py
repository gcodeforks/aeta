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

"""Tests for the handlers module of aeta."""



# Disable checking; pylint:disable-msg=C0111,C0103,W0212
# pylint:disable-msg=C0103,R0902,R0201,R0904
# - docstrings
# - access to protected members
# - too many public methods
# - setUp() and tearDown() method names
# - too many instance attributes
# - method could be a function

import unittest

from google.appengine.ext import webapp

from aeta import handlers
from tests import utils


class BaseRequestHandlerTest(unittest.TestCase, utils.HandlerTestMixin):
  """Tests for the BaseRequestHandler class."""

  def setUp(self):
    self.handler = handlers.BaseRequestHandler()
    self.request = webapp.Request({})
    self.response = webapp.Response()
    self.handler.initialize(self.request, self.response)

  def test_render_error_wrong_input(self):
    self.assertRaises(TypeError, self.handler.render_error, 0, 0)
    self.assertRaises(TypeError, self.handler.render_error, '', '')
    self.assertRaises(TypeError, self.handler.render_error, None, 0)
    self.assertRaises(TypeError, self.handler.render_error, '', None)

  def check_render_error(self, msg, status):
    self.handler.render_error(msg, status)
    resp = self.handler.response
    resp_status = getattr(resp, 'status_int', None) or resp.status
    self.assertEqual(status, resp_status)
    self.check_response(resp, msg, False)

  def test_render_error(self):
    self.check_render_error('a sample message', 400)

  def test_render_error_unicode(self):
    self.check_render_error(u'a sample message', 500)

  def test_render_error_long_status_code(self):
    self.check_render_error('a sample message', long(400))

  def test_render_page_wrong_input(self):
    self.assertRaises(TypeError, self.handler.render_page, {}, {})
    self.assertRaises(TypeError, self.handler.render_page, '', '')
    self.assertRaises(TypeError, self.handler.render_page, None, {})
    self.assertRaises(TypeError, self.handler.render_page, '', None)

  def test_render_page(self):
    template_file = handlers._get_template_path('index.html')
    values = {'title': 'bar'}
    self.handler.render_page(template_file, values)
    self.check_response(self.handler.response, 'bar', False)
