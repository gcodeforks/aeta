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

"""Unit tests for the rest module of aeta."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

# Disable checking; pylint:disable-msg=C0111,W0212,R0904,C0103
# - docstrings
# - access to protected members
# - too many public methods
# - setUp() and tearDown() method names

import copy
import unittest

from google.appengine.ext import ndb
from google.appengine.ext import testbed
from google.appengine.ext import webapp
import webtest

try:
  import json
except ImportError:
  import simplejson as json

from aeta import config
from aeta import models
from aeta import rest
from aeta import runner
from tests import utils


class GetBatchResultsTest(unittest.TestCase, utils.MockAttributeMixin):
  """Tests for get_batch_results."""

  def setUp(self):
    self.batch = None
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.config = copy.copy(config.get_config())

  def tearDown(self):
    self.testbed.deactivate()
    self.tear_down_attributes()

  def make_tasks(self, finished_indexes):
    self.batch.put()
    for i in range(self.batch.num_units):
      task = models.RunTestUnitTask(fullname='test%s' % i)
      task.key = models.RunTestUnitTask.get_key(self.batch.key, i)
      if i in finished_indexes:
        task.set_json({'index': i}, self.config)
      task.put()

  def test_first(self):
    self.batch = models.TestBatch(fullname='some.module', num_units=10)
    self.make_tasks([0, 1, 2, 4, 5, 7])
    results = rest.get_batch_results(self.batch, 0)
    self.assertEqual([{'index': 0}, {'index': 1}, {'index': 2}], results)

  def test_middle(self):
    self.batch = models.TestBatch(fullname='some.module', num_units=10)
    self.make_tasks([0, 1, 2, 3, 4, 6])
    results = rest.get_batch_results(self.batch, 2)
    self.assertEqual([{'index': 2}, {'index': 3}, {'index': 4}], results)

  def test_no_new(self):
    self.batch = models.TestBatch(fullname='some.module', num_units=10)
    self.make_tasks([0, 1, 2, 4, 5, 7])
    results = rest.get_batch_results(self.batch, 3)
    self.assertEqual([], results)

  def test_last(self):
    self.batch = models.TestBatch(fullname='some.module', num_units=5)
    self.make_tasks([0, 1, 2, 3, 4])
    results = rest.get_batch_results(self.batch, 3)
    self.assertEqual([{'index': 3}, {'index': 4}], results)


# self.handler has to be initialized by child class -
# pylint:disable-msg=E1101
class HandlerTestBase(unittest.TestCase, utils.HandlerTestMixin,
                      utils.MockAttributeMixin, utils.TestDataMixin):
  """Base class for handler tests.

  When using this base class, set 'self.handler' first. then invoke
  the base setUp method.
  """

  def setUp(self):
    self.url_path = '/tests/'
    app = webapp.WSGIApplication(rest.get_handler_mapping(self.url_path))
    self.app = webtest.TestApp(app)
    self.setup_test_data()
    self.config = copy.copy(config.get_config())
    self.config.test_package_names = [self.test_package_name]

    @self.mock(config)
    def get_config():
      return self.config

  def tearDown(self):
    self.tear_down_test_data()
    self.tear_down_attributes()

  def check_response_text_not_expected(self, response, not_expected_output):
    self.assertNotEqual(not_expected_output, response.body)


class GetMethodsRequestHandlerTest(HandlerTestBase):
  """Tests for the GetMethodsRequestHandler class."""

  def setUp(self):
    HandlerTestBase.setUp(self)
    self.handler_path = self.url_path + 'get_methods/'
    self.setup_test_data()

  def test_success(self):
    fullname = 'sample_package.test_one_testcase'
    resp = self.app.get(self.handler_path + fullname, status=200)
    exp_resp = {'method_names': [fullname + '.SimpleTestCase.test_fail',
                                 fullname + '.SimpleTestCase.test_pass'],
                'load_errors': []}
    self.check_response(resp, exp_resp, is_json=True)

  def test_invalid_name(self):
    fullname = 'does.not.exist'
    resp = self.app.get(self.handler_path + fullname, status=200)
    resp_json = json.loads(resp.body)
    self.assertEqual([], resp_json['method_names'])
    self.assertEqual(1, len(resp_json['load_errors']))
    self.assertEqual('does.not.exist', resp_json['load_errors'][0][0])

  def test_load_error(self):
    fullname = 'sample_package.test_brokenmodule'
    resp = self.app.get(self.handler_path + fullname, status=200)
    resp_json = json.loads(resp.body)
    self.assertEqual([], resp_json['method_names'])
    self.assertEqual(1, len(resp_json['load_errors']))
    self.assertEqual('sample_package.test_brokenmodule',
                     resp_json['load_errors'][0][0])


class StartBatchRequestHandlerTest(HandlerTestBase):
  """Tests for the StartBatchRequestHandler class."""

  def setUp(self):
    HandlerTestBase.setUp(self)
    self.handler_path = self.url_path + 'start_batch/'
    self.batch_id = 1234
    self.fullname = None
    self.config = copy.copy(config.get_config())
    self.config.storage = 'datastore'
    self.mock(config, 'get_config')(lambda: self.config)

    @self.mock(runner)
    def start_batch(fullname, conf):
      self.assertEqual(self.fullname, fullname)
      self.assertEqual(self.config, conf)
      key = ndb.Key(models.TestBatch, self.batch_id)
      return models.TestBatch(fullname=fullname, key=key)

  def test_success(self):
    self.fullname = 'sample_package.test_goodmodule'
    resp = self.app.post(self.handler_path + self.fullname, status=200)
    self.check_response(resp, {'batch_id': str(self.batch_id)}, is_json=True)

  def test_run_everything(self):
    self.fullname = ''
    resp = self.app.post(self.handler_path, status=200)
    self.check_response(resp, {'batch_id': str(self.batch_id)}, is_json=True)

  def test_invalid_name(self):
    self.fullname = 'does.not.exist'
    resp = self.app.post(self.handler_path + self.fullname, status=404)
    self.check_response_text_not_expected(resp, '')

  def test_load_error(self):
    self.fullname = 'sample_package.test_brokenmodule'
    resp = self.app.post(self.handler_path + self.fullname, status=500)
    self.check_response_text_not_expected(resp, '')

  def test_immediate(self):
    self.fullname = 'sample_package'
    self.config.storage = 'immediate'
    load_errors = [('sample_package.badmodule', 'ImportError')]
    test_unit_methods = {'sample_package.goodmodule':
                         ['sample_package.goodmodule.Class.method']}

    @self.mock(runner)
    def start_batch(fullname, conf):
      self.assertEqual(self.fullname, fullname)
      self.assertEqual(self.config, conf)
      key = ndb.Key(models.TestBatch, self.batch_id)
      batch = models.TestBatch(fullname=fullname, key=key, num_units=1)
      ctx_options = models.get_ctx_options(conf)
      batch.put(**ctx_options)
      batch.set_info(load_errors, test_unit_methods, conf)
      batch.put(**ctx_options)
      task_key = models.RunTestUnitTask.get_key(batch.key, 0)
      task = models.RunTestUnitTask(key=task_key,
                                    fullname='sample_package.goodmodule')
      task.put(**ctx_options)
      # Fake result JSON rather than from set_test_result().
      task.set_json({'result': 'passed'}, conf)
      task.put(**ctx_options)
      return batch

    resp = self.app.post(self.handler_path + self.fullname, status=200)
    self.check_response(resp, {
        'batch_info': {'load_errors': load_errors,
                       'num_units': 1,
                       'test_unit_methods': test_unit_methods},
        'results': [{'result': 'passed'}]
        }, is_json=True)


class BatchInfoRequestHandlerTest(HandlerTestBase):
  """Tests for the BatchInfoRequestHandler class."""

  def setUp(self):
    self.handler = rest.BatchInfoRequestHandler()
    HandlerTestBase.setUp(self)
    self.handler_path = self.url_path + 'batch_info/'
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.config = copy.copy(config.get_config())

  def tearDown(self):
    self.testbed.deactivate()
    HandlerTestBase.tearDown(self)

  def test_batch_info(self):
    batch = models.TestBatch(fullname='tests', num_units=5)
    batch.key = ndb.Key(models.TestBatch, 'batchid')
    batch.put()
    load_errors = [('tests.badmodule', 'ImportError')]
    test_unit_methods = {'tests': ['tests.module.TestCase.method']}
    batch.set_info(load_errors, test_unit_methods, self.config)
    batch.put()
    resp = self.app.get(self.handler_path + 'batchid', status=200)
    self.check_response(resp,
                        {'num_units': 1,
                         'test_unit_methods': test_unit_methods,
                         'load_errors': load_errors},
                        is_json=True)

  def test_bad_id(self):
    resp = self.app.get(self.handler_path + '111', status=404)
    self.check_response_text_not_expected(resp, '')


class BatchResultsRequestHandlerTest(HandlerTestBase):
  """Tests for the BatchResultsRequestHandler class."""

  def setUp(self):
    self.handler = rest.BatchResultsRequestHandler()
    HandlerTestBase.setUp(self)
    self.handler_path = self.url_path + 'batch_results/'
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()

  def tearDown(self):
    self.testbed.deactivate()
    HandlerTestBase.tearDown(self)

  def test_batch_results(self):
    batch = models.TestBatch(fullname='tests', num_units=5)
    batch.key = ndb.Key(models.TestBatch, 'batchid')
    batch.put()

    @self.mock(rest)
    def get_batch_results(bat, start):
      self.assertEqual(batch, bat)
      self.assertEqual(3, start)
      return ['result1', 'result2']
    resp = self.app.get('%s%s?start=3' % (self.handler_path, 'batchid'),
                        status=200)
    self.check_response(resp, ['result1', 'result2'], is_json=True)

  def test_bad_id(self):
    resp = self.app.get(self.handler_path + '111?start=3', status=404)
    self.check_response_text_not_expected(resp, '')

  def test_start_not_integer(self):
    batch = models.TestBatch(fullname='tests', num_units=5)
    batch.key = ndb.Key(models.TestBatch, 'batchid')
    batch.put()
    resp = self.app.get('%s%s?start=notaninteger' %
                        (self.handler_path, 'batchid'), status=400)
    self.check_response_text_not_expected(resp, '')

  def test_start_negative(self):
    batch = models.TestBatch(fullname='tests', num_units=5)
    batch.key = ndb.Key(models.TestBatch, 'batchid')
    batch.put()
    resp = self.app.get('%s%s?start=-5' % (self.handler_path, 'batchid'),
                        status=400)
    self.check_response_text_not_expected(resp, '')

  def test_start_too_high(self):
    batch = models.TestBatch(fullname='tests', num_units=5)
    batch.key = ndb.Key(models.TestBatch, 'batchid')
    batch.put()
    resp = self.app.get('%s%s?start=5' % (self.handler_path, 'batchid'),
                        status=400)
    self.check_response_text_not_expected(resp, '')
