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

"""Tests for the main module of aeta."""

__author__ = 'jacobltaylor@google.com (Jacob Taylor)'

import copy
import unittest

from google.appengine.api import users
from google.appengine.ext import testbed
import webtest

from aeta import config
from aeta import main
from tests import utils


class AuthWsgiMiddlewareTest(unittest.TestCase, utils.MockAttributeMixin):
  """Tests for the AuthWsgiMiddleware class."""

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_user_stub()
    self.config = copy.copy(config.get_config())
    self.config.protected = True
    self.url = '/tests/'
    self.is_current_user_admin = False
    self.current_user = users.User(email='user@example.com')

    @self.mock(config)
    def get_config():
      return self.config

    @self.mock(users)
    def is_current_user_admin():
      return self.is_current_user_admin

    @self.mock(users)
    def get_current_user():
      return self.current_user

    def inner(environ, start_response):
      start_response('200 OK', [('Content-Type', 'text/html')])
      return ['content']

    self.app = webtest.TestApp(main.AuthWsgiMiddleware(inner))

  def tearDown(self):
    self.tear_down_attributes()
    self.testbed.deactivate()

  def check_success(self, environ):
    response = self.app.get(self.url, extra_environ=environ, status=200)
    self.assertEqual('content', response.body)

  def check_fail(self, environ):
    response = self.app.get(self.url, extra_environ=environ, status=302)
    self.assertNotEqual('content', response.body)
    self.assertTrue(response.headers.get('Location'))

  def test_not_protected(self):
    self.config.protected = False
    self.current_user = None
    self.check_success({})

  def test_admin(self):
    self.is_current_user_admin = True
    self.check_success({})

  def test_not_logged_in(self):
    self.current_user = None
    self.check_fail({})

  def test_non_admin(self):
    self.check_fail({})

  def test_non_admin_with_permission(self):
    self.config.permitted_emails = ['user@example.com']
    self.check_success({})

  def test_dev_server(self):
    self.current_user = None
    self.check_success({'SERVER_SOFTWARE': 'Development'})

  def test_task_queue(self):
    self.current_user = None
    self.check_success({'HTTP_X_APPENGINE_TASKNAME': '123'})






