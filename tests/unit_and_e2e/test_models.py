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

"""Tests for the models module of aeta."""



# Disable checking; pylint: disable-msg=C0111,W0212,R0904,C0103
# - docstrings
# - access to protected members
# - too many public methods
# - setUp() and tearDown() method names

import copy
import os
import unittest

from google.appengine.ext import blobstore
from google.appengine.ext import ndb
from google.appengine.ext import testbed

from aeta import config
from aeta import models
from aeta import task_deferred as deferred
from tests import utils


class JsonHolderTest(unittest.TestCase, utils.MockAttributeMixin):
  """Tests for the JsonHolder class."""

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_files_stub()
    if not os.environ.get('SERVER_SOFTWARE', '').startswith('Dev'):
      # Testbed blobstore doesn't work on the development server.
      self.testbed.init_blobstore_stub()
    self.holder = models.JsonHolder()
    self.config = copy.copy(config.get_config())
    self.cleaned_up = False

    @self.mock(deferred)
    def defer(func, *args, **kwargs):
      self.assertEqual(self.config.test_queue, kwargs.pop('_queue'))
      self.assertTrue(kwargs.pop('_countdown') > 10)
      self.assertEqual({}, kwargs)
      self.assertEqual(models._delete_blob_if_done, func)
      self.assertEqual(3, len(args))
      self.assertEqual(self.holder.key, args[0])
      self.assertTrue(isinstance(args[1], blobstore.BlobKey))
      self.assertEqual(self.config, args[2])
      self.cleaned_up = True

  def tearDown(self):
    if self.holder.blob_key:
      blobstore.delete(self.holder.blob_key)
    self.testbed.deactivate()
    self.tear_down_attributes()

  def test_not_set(self):
    self.holder.put()
    self.assertEqual(None, self.holder.get_json())

  def test_set_small(self):
    json = {'a': 'b'}
    self.holder.put()
    self.holder.set_json(json, self.config)
    self.holder = self.holder.put().get()
    self.assertEqual(json, self.holder.get_json())
    self.assertFalse(self.cleaned_up)

  def test_set_large(self):
    json = 'a' * 2000000
    self.holder.put()
    self.holder.set_json(json, self.config)
    self.holder = self.holder.put().get()
    self.assertEqual(json, self.holder.get_json())
    self.assertTrue(blobstore.BlobInfo.get(self.holder.blob_key))
    self.assertTrue(self.cleaned_up)

  def test_set_no_key(self):
    self.assertRaises(ValueError, self.holder.set_json, 'json', self.config)


class TestBatchTest(unittest.TestCase, utils.MockAttributeMixin):
  """Tests for the TestBatch class."""

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.config = copy.copy(config.get_config())

  def tearDown(self):
    self.testbed.deactivate()
    self.tear_down_attributes()

  def test_get_tasks(self):
    batch = models.TestBatch(fullname='tests', num_units=3)
    batch.put()
    task1 = models.RunTestUnitTask(fullname='tests.first')
    task1.key = models.RunTestUnitTask.get_key(batch.key, 0)
    task1.put()
    task2 = models.RunTestUnitTask(fullname='tests.second')
    task2.key = models.RunTestUnitTask.get_key(batch.key, 1)
    task2.put()
    self.assertEqual([task1, task2, None], batch.get_tasks(self.config))

  def test_unknown_num_units(self):
    batch = models.TestBatch(fullname='tests')
    batch.put()
    self.assertEqual(None, batch.get_tasks(self.config))

  def test_set_info(self):
    load_errors = [('tests.badmodule', 'ImportError')]
    test_unit_methods = {
        'tests.goodmodule.Class1': ['tests.goodmodule.Class1.method'],
        'tests.goodmodule.Class2': ['tests.goodmodule.Class2.method']
    }
    self.did_set = False

    @self.mock(models.JsonHolder)
    def set_json(holder_self, data, conf):
      self.assertEqual(self.config, conf)
      self.assertEqual(
          {'num_units': 2, 'load_errors': load_errors,
           'test_unit_methods': test_unit_methods}, data)
      self.did_set = True

    batch = models.TestBatch(fullname='tests', num_units=2)
    batch.put()
    batch.set_info(load_errors, test_unit_methods, self.config)
    self.assertTrue(self.did_set)


class RunTestUnitTaskTest(unittest.TestCase, utils.MockAttributeMixin):
  """Tests for the RunTestUnitTask class."""

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.config = copy.copy(config.get_config())

  def tearDown(self):
    self.testbed.deactivate()
    self.tear_down_attributes()

  def test_get_key_invalid_arguments(self):
    batch = models.TestBatch(fullname='tests', num_units=3)
    batch.put()
    self.assertRaises(TypeError, models.RunTestUnitTask.get_key, None, 5)
    self.assertRaises(TypeError, models.RunTestUnitTask.get_key, batch.key,
                      None)

  def test_get_key(self):
    batch = models.TestBatch(fullname='tests', num_units=3)
    batch.put()
    k = models.RunTestUnitTask.get_key(batch.key, 1)
    self.assertTrue(isinstance(k, ndb.Key))
    k_same = models.RunTestUnitTask.get_key(batch.key, 1)
    self.assertEqual(k, k_same)
    k2 = models.RunTestUnitTask.get_key(batch.key, 2)
    self.assertNotEqual(k, k2)

  def test_set_result(self):
    load_errors = [('tests.badmodule', 'ImportError')]
    testresult = unittest.TestResult()
    # We need test cases, so we might as well use the ones defined here.
    class_name = '%s.RunTestUnitTaskTest' % type(self).__module__
    error_case = RunTestUnitTaskTest('test_get_key')
    error_case.fullname = '%s.test_get_key' % class_name
    failure_case = RunTestUnitTaskTest('test_set_result')
    failure_case.fullname = '%s.test_set_result' % class_name
    # Changing the class name (and therefore the id()s of the test cases)
    # should not affect the results.
    self.mock(type(self), '__name__')('SomeOtherClass')
    testresult.errors = [(error_case, 'error')]
    testresult.failures = [(failure_case, 'failure')]
    output = 'some output'
    self.did_set = False

    @self.mock(models.JsonHolder)
    def set_json(holder_self, data, conf):
      self.assertEqual(self.config, conf)
      self.assertEqual(
          {'fullname': 'tests.module', 'load_errors': load_errors,
           'errors': [(error_case.fullname, 'error')],
           'failures': [(failure_case.fullname, 'failure')],
           'output': output}, data)

      self.did_set = True

    batch = models.TestBatch(fullname='tests', num_units=2)
    batch.put()
    task = models.RunTestUnitTask(
        key=models.RunTestUnitTask.get_key(batch.key, 1),
        fullname='tests.module')
    task.set_test_result(load_errors, testresult, output, self.config)
    self.assertTrue(self.did_set)


class DeleteBlobIfDoneTest(unittest.TestCase, utils.MockAttributeMixin):
  """Tests for the _delete_blob_if_done function."""

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_datastore_v3_stub()
    self.testbed.init_memcache_stub()
    self.testbed.init_files_stub()
    if not os.environ.get('SERVER_SOFTWARE', '').startswith('Dev'):
      # Testbed blobstore doesn't work on the development server.
      self.testbed.init_blobstore_stub()
    self.config = copy.copy(config.get_config())
    self.did_defer = False
    self.holder = models.JsonHolder()
    self.holder.put()

    # Ignore deferral caused by set_json.
    @self.mock(deferred)
    def defer(func, *args, **kwargs):
      pass

    self.holder.set_json('a' * 2000000, self.config)

    @self.mock(deferred)
    def defer(func, *args, **kwargs):
      self.assertEqual(self.config.test_queue, kwargs.pop('_queue'))
      self.assertTrue(kwargs.pop('_countdown') > 10)
      self.assertEqual({}, kwargs)
      self.assertEqual(models._delete_blob_if_done, func)
      self.assertEqual(3, len(args))
      self.assertEqual(self.holder.key, args[0])
      self.assertTrue(isinstance(args[1], blobstore.BlobKey))
      self.assertEqual(self.config, args[2])
      self.did_defer = True

  def tearDown(self):
    self.testbed.deactivate()
    self.tear_down_attributes()

  def test_delete(self):
    self.holder.key.delete()
    models._delete_blob_if_done(self.holder.key, self.holder.blob_key,
                                self.config)
    self.assertEqual(None, blobstore.BlobInfo.get(self.holder.blob_key))
    self.assertFalse(self.did_defer)

  def test_defer(self):
    models._delete_blob_if_done(self.holder.key, self.holder.blob_key,
                                self.config)
    self.assertNotEqual(None, blobstore.BlobInfo.get(self.holder.blob_key))
    self.assertTrue(self.did_defer)

