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

"""Tests for the task_deferred module of aeta."""

__author__ = 'jacobltaylor@google.com (Jacob Taylor)'

import os
import time
import unittest

from google.appengine.api import taskqueue
from google.appengine.ext import webapp
import webtest

from aeta import config
from aeta import task_deferred as deferred
from tests import utils


# Arguments to the deferred function will append to this list of (args, kwargs)
# pairs.  This is to make sure the function was called with the right
# arguments.
_deferred_args = []

# It's important for this to be a global function rather than a local
# function/method, to reflect actual usage.
def _add_deferred_args(*args, **kwargs):
  _deferred_args.append((args, kwargs))


def get_args(*args, **kwargs):
  return (args, kwargs)


class DeferredTest(unittest.TestCase, utils.MockAttributeMixin):
  """Test for deferring a task and then running it."""

  def setUp(self):
    self.payloads = []
    self.expected_queue_name = 'default'
    self.expected_countdown = 0
    self.url = config.get_config().url_path_deferred
    app = webapp.WSGIApplication([(self.url, deferred.DeferredHandler)])
    self.app = webtest.TestApp(app)
    self.environ = {'HTTP_X_APPENGINE_TASKNAME': '123'}
    self.mock(os, 'environ')(self.environ)

    @self.mock(taskqueue.Queue)
    def add(queue_self, task):

      def add_task(tsk):
        self.assertEqual(config.get_config().url_path_deferred, tsk.url)
        self.assertEqual(self.expected_queue_name, queue_self.name)
        countdown_diff = tsk.eta_posix - time.time()
        self.assertTrue(abs(self.expected_countdown - countdown_diff) < 10)
        self.payloads.append(tsk.payload)

      if isinstance(task, list):
        self.assertTrue(len(task) <= taskqueue.MAX_TASKS_PER_ADD)
        for tsk in task:
          add_task(tsk)
      else:
        add_task(task)

  def tearDown(self):
    self.tear_down_attributes()

  def check_execute_task(self, *expected_args):
    global _deferred_args
    _deferred_args = []
    for payload in self.payloads:
      self.app.post(self.url, payload, extra_environ=self.environ)
    self.assertEqual(list(expected_args), _deferred_args)

  def test_defaults(self):
    deferred.defer(_add_deferred_args, 1, x=5)
    self.check_execute_task(get_args(1, x=5))

  def test_set_queue(self):
    self.expected_queue_name = 'myqueue'
    deferred.defer(_add_deferred_args, 'hi', y=0, _queue='myqueue')
    self.check_execute_task(get_args('hi', y=0))

  def test_set_countdown(self):
    self.expected_countdown = 1000
    deferred.defer(_add_deferred_args, x=5, y=6, _countdown=1000)
    self.check_execute_task(get_args(x=5, y=6))

  def test_multi_small(self):
    deferred.defer_multi([
      deferred.DeferredCall(_add_deferred_args, 5, 6),
      deferred.DeferredCall(_add_deferred_args, 7, x='the'),
      deferred.DeferredCall(_add_deferred_args, x=1, y=2)])
    self.check_execute_task(get_args(5, 6), get_args(7, x='the'),
                            get_args(x=1, y=2))

  def test_multi_large(self):
    num_tasks = int(2.5 * taskqueue.MAX_TASKS_PER_ADD)
    calls = [deferred.DeferredCall(_add_deferred_args, x=x)
             for x in range(num_tasks)]
    deferred.defer_multi(calls)
    exp_args = [get_args(x=x) for x in range(num_tasks)]
    self.check_execute_task(*exp_args)

  def test_not_task_queue(self):
    del self.environ['HTTP_X_APPENGINE_TASKNAME']
    self.app.post(self.url, '', status=403)

