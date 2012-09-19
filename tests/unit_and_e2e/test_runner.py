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

"""Tests for the runner module of aeta."""



import copy
import sys
import time
import unittest

from google.appengine.ext import ndb
from google.appengine.ext import testbed

from aeta import config
from aeta import logic
from aeta import models
from aeta import runner
from aeta import task_deferred as deferred
from tests import utils


class RunTestAndCaptureOutputTest(unittest.TestCase):
  """Tests for _run_test_and_capture_output."""

  def setUp(self):
    self.orig_stdout = runner.sys.stdout
    self.orig_stderr = runner.sys.stderr

  def tearDown(self):
    runner.sys.stdout = self.orig_stdout
    runner.sys.stderr = self.orig_stderr

  def test_invalid_input(self):
    for invalid in [None, 0, []]:
      self.assertRaises(TypeError, runner._run_test_and_capture_output,
                        invalid)

  def test_test_result(self):

    class Test(unittest.TestCase):

      def test_foo(self):
        self.assertTrue(True)

      def test_bar(self):
        self.assertTrue(False)

      def test_baz(self):
        raise ValueError

    suite = unittest.makeSuite(Test)
    testresult, _ = runner._run_test_and_capture_output(suite)
    self.assertEqual(3, testresult.testsRun)
    self.assertEqual(1, len(testresult.failures))
    self.assertEqual(1, len(testresult.errors))

  def test_restored_redirects(self):

    class Test(unittest.TestCase):

      def test_foo(self):
        raise ValueError

    suite = unittest.makeSuite(Test)
    runner._run_test_and_capture_output(suite)
    self.assertEqual(self.orig_stdout, runner.sys.stdout)
    self.assertEqual(self.orig_stderr, runner.sys.stderr)

  def test_stdout_redirect(self):
    expected_output = 'hello world'

    class Test(unittest.TestCase):

      def test_foo(self):
        print expected_output

    suite = unittest.makeSuite(Test)
    _, output = runner._run_test_and_capture_output(suite)
    self.assertTrue(expected_output in output)

  def test_stderr_redirect(self):
    expected_output = 'hello world'

    class Test(unittest.TestCase):

      def test_foo(self):
        print >> sys.stderr, expected_output

    suite = unittest.makeSuite(Test)
    _, output = runner._run_test_and_capture_output(suite)
    self.assertTrue(expected_output in output)


class RunTestUnitTest(unittest.TestCase, utils.MockAttributeMixin):
  """Tests for _run_test_unit."""

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.config = copy.copy(config.get_config())
    self.batch = None

    self.test_fullname = None
    self.test_method_names = None
    self.load_errors = []

    class MockTestObject(object):

      def get_suite(test_self, conf, errors_out=None):
        self.assertEqual(self.config, conf)
        if errors_out is not None:
          errors_out.extend(self.load_errors)
        # For a TestSuite we need some TestCases, so we might as well use the
        # ones defined in this class.
        cases = [RunTestUnitTest(name) for name in self.test_method_names]
        return unittest.TestSuite(cases)

    @self.mock(logic)
    def get_requested_object(name, conf):
      self.assertEqual(self.test_fullname, name)
      return MockTestObject()

    @self.mock(runner)
    def _run_test_and_capture_output(suite):
      test_names = [case.id().split('.')[-1] for case in suite]
      self.assertEqual(self.test_method_names, test_names)
      test_result = unittest.TestResult()
      return test_result, 'some output'

  def tearDown(self):
    self.testbed.deactivate()
    self.tear_down_attributes()

  def check_run_test_unit(self, index):
    task_key = models.RunTestUnitTask.get_key(self.batch.key, index)
    runner._run_test_unit(self.test_fullname, task_key, self.config)
    task = task_key.get()
    json = task.get_json()
    self.assertTrue(isinstance(json, dict))
    self.assertEqual('some output', json['output'])

  def test_one_unit(self):
    self.batch = models.TestBatch(fullname='tests', num_units=1)
    self.batch.put()
    self.test_fullname = 'something.RunTestUnitTest'
    self.test_method_names = ['test_one_unit', 'test_two_units']
    self.check_run_test_unit(0)

  def test_two_units(self):
    self.batch = models.TestBatch(fullname='tests', num_units=2)
    self.batch.put()
    self.test_fullname = 'something.RunTestUnitTest.test_one_unit'
    self.test_method_names = ['test_one_unit']
    self.check_run_test_unit(0)
    self.test_fullname = 'something.RunTestUnitTest.test_two_units'
    self.test_method_names = ['test_two_units']
    self.check_run_test_unit(1)

  def test_load_error(self):
    self.batch = models.TestBatch(fullname='tests', num_units=1)
    self.batch.put()
    self.test_fullname = 'something.RunTestUnitTest'
    self.test_method_names = ['test_one_unit', 'test_two_units']
    self.load_errors = [('badmodule', 'ImportError')]
    self.check_run_test_unit(0)


class DeleteBatchTest(unittest.TestCase, utils.MockAttributeMixin):
  """Tests for _delete_batch."""

  def setUp(self):
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.config = copy.copy(config.get_config())
    self.count_deferred = 0
    self.batch = None
    self.exp_num_done = None

    @self.mock(deferred)
    def defer(func, batch_key, num_done, config, _queue, _countdown):
      self.assertEqual(runner._delete_batch, func)
      self.assertEqual(self.batch.key, batch_key)
      self.assertEqual(self.exp_num_done, num_done)
      self.assertEqual(self.config, config)
      self.assertEqual(self.config.test_queue, _queue)
      self.assertEqual(runner._DELETE_TIME_SECS, _countdown)
      self.count_deferred += 1

  def tearDown(self):
    self.testbed.deactivate()
    self.tear_down_attributes()

  def test_already_done(self):
    self.batch = models.TestBatch(fullname='tests', num_units=1)
    self.batch.put()
    task = models.RunTestUnitTask(fullname='tests.unit')
    task.key = models.RunTestUnitTask.get_key(self.batch.key, 0)
    task.put()
    self.exp_num_done = 1
    # This shouldn't delete anything yet.
    runner._delete_batch(self.batch.key, 0, self.config)
    self.assertEqual(self.batch, self.batch.key.get())
    self.assertEqual(task, task.key.get())
    self.assertEqual(1, self.count_deferred)
    runner._delete_batch(self.batch.key, 1, self.config)
    # Now everything should be deleted.
    self.assertEqual(None, self.batch.key.get())
    self.assertEqual(None, task.key.get())
    self.assertEqual(1, self.count_deferred)

  def test_no_progress(self):
    self.batch = models.TestBatch(fullname='tests', num_units=1)
    self.batch.put()
    self.exp_num_done = 0
    runner._delete_batch(self.batch.key, 0, self.config)
    # Now everything should be deleted.
    self.assertEqual(None, self.batch.key.get())
    self.assertEqual(0, self.count_deferred)

  def test_already_deleted(self):
    self.batch = models.TestBatch(fullname='tests', num_units=1)
    self.batch.put()
    self.batch.key.delete()
    # This should do nothing.
    runner._delete_batch(self.batch.key, 1, self.config)


class InitializeBatchTest(unittest.TestCase, utils.TestDataMixin,
                          utils.MockAttributeMixin):
  """Tests for _initialize_batch."""

  def setUp(self):
    self.setup_test_data()
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.config = copy.copy(config.get_config())
    self.config.storage = 'datastore'

    self.result = unittest.TestResult()
    self.output = 'some test output'

    self.deferred = []

    @self.mock(deferred)
    def defer_multi(calls, queue):
      self.assertEqual(self.config.test_queue, queue)
      self.deferred.extend(calls)

    self.fullname = None
    self.test_unit_methods = {}

    class MockTestObject(object):

      def __init__(test_self, fullname):
        test_self.fullname = fullname

      def get_units(test_self, conf, errors_out=None):
        self.assertEqual(self.fullname, test_self.fullname)
        return [MockTestObject(unit) for unit in self.test_unit_methods]

      def get_suite(test_self, conf, errors_out=None):
        # This would normally return a TestSuite but we return a dictionary
        # instead.
        return {'methods': self.test_unit_methods[test_self.fullname]}

      def get_methods(test_self, conf, errors_out=None):
        methods = self.test_unit_methods[test_self.fullname]
        return [MockTestObject(method) for method in methods]

    @self.mock(logic)
    def get_requested_object(fullname, conf):
      return MockTestObject(fullname)

  def tearDown(self):
    self.tear_down_test_data()
    self.testbed.deactivate()
    self.tear_down_attributes()

  def check_initialize_batch(self):
    batch = models.TestBatch(fullname=self.fullname)
    batch.put()
    runner._initialize_batch(batch.fullname, batch.key, self.config)
    batch = batch.key.get()
    self.assertEqual(self.fullname, batch.fullname)
    self.assertEqual(len(self.test_unit_methods), batch.num_units)
    json = batch.get_json()
    self.assertTrue(isinstance(json, dict))
    self.assertEqual(self.test_unit_methods, json['test_unit_methods'])
    self.assertEqual(len(self.test_unit_methods) + 1, len(self.deferred))
    for name, call in zip(self.test_unit_methods, self.deferred):
      self.assertEqual({}, call.kwargs)
      self.assertEqual(runner._run_test_unit, call.func)
      self.assertEqual(name, call.args[0])
      self.assertTrue(isinstance(call.args[1], ndb.Key))
      self.assertEqual(self.config, call.args[2])
    last_call = self.deferred[-1]
    self.assertEqual(runner._delete_batch, last_call.func)
    self.assertEqual((batch.key, 0, self.config), last_call.args)
    self.assertTrue(last_call.countdown > 0)

  def test_normal(self):
    self.fullname = 'test.package'
    self.test_unit_methods = {
        'test.package.module1': ['test.package.module1.TestCase.method1',
                                 'test.package.module1.TestCase.method2'],
        'test.package.module2': ['test.package.module2.FirstTest.method',
                                 'test.package.module2.SecondTest.method']
    }
    self.check_initialize_batch()

  def test_different_queue(self):
    self.config.test_queue = 'some_other_queue'
    self.fullname = 'tests'
    self.test_unit_methods = {'tests.module': ['tests.module.Case.method']}
    self.check_initialize_batch()


class StartBatchTest(unittest.TestCase, utils.MockAttributeMixin):

  def setUp(self):
    self.config = copy.copy(config.get_config())
    self.config.storage = 'datastore'
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.deferred = []

    @self.mock(deferred)
    def defer_multi(calls, queue='default'):
      self.assertEqual(self.config.test_queue, queue)
      self.deferred.extend(calls)

  def tearDown(self):
    self.testbed.deactivate()
    self.tear_down_attributes()

  def test_start_batch(self):
    batch = runner.start_batch('tests.module', self.config)
    self.assertEqual('tests.module', batch.fullname)
    self.assertEqual(1, len(self.deferred))
    self.assertEqual(runner._initialize_batch, self.deferred[0].func)
    self.assertEqual(('tests.module', batch.key, self.config),
                     self.deferred[0].args)


class RunnerE2ETest(unittest.TestCase, utils.TestDataMixin,
                    utils.MockAttributeMixin):
  """End-to-end tests for running test batches with "immediate" setting."""

  # pylint:disable-msg=C0103
  def setUp(self):
    self.setup_test_data()
    self.module_name = self.test_package_name + '.test_one_testcase'
    self.test_class_name = self.module_name + '.SimpleTestCase'
    self.test_method_name = self.test_class_name + '.test_pass'
    self.testbed = testbed.Testbed()
    self.testbed.activate()
    self.testbed.init_memcache_stub()
    self.testbed.init_datastore_v3_stub()
    self.config = copy.copy(config.get_config())
    self.config.test_package_names = [self.test_package_name]
    self.config.test_module_pattern = '^test_[\w]+$'

    @self.mock(deferred)
    def defer_multi(calls, queue):
      if calls:
        raise Exception('should not defer when storage = "immediate"')

  # pylint:disable-msg=C0103
  def tearDown(self):
    self.tear_down_test_data()
    self.testbed.deactivate()
    self.tear_down_attributes()

  def run_tests(self, fullname):
    """Runs tests and returns results."""
    self.config.storage = 'immediate'
    batch = runner.start_batch(fullname, self.config)
    self.assertTrue(isinstance(batch.get_json(), dict))
    return [task.get_json() for task in batch.get_tasks(self.config)]

  def test_empty_name(self):
    self.config.parallelize_classes = True
    self.config.parallelize_methods = True
    subpackage = self.test_package_name + '.subpackage'
    self.config.test_package_names = [subpackage]
    results = self.run_tests('')
    self.assertEqual(2, len(results))
    names = sorted(res['fullname'] for res in results)
    self.assertEqual([subpackage + '.test_ham.FooTest.test_fail',
                      subpackage + '.test_ham.FooTest.test_pass'], names)

  # TODO(user): remove or fix this method or fix behavior.
  # def test_test_module_with_no_test_cases(self):
  #   fullname = self.test_package_name + '.no_testcase_test'
  #   results = runner.load_and_run_tests(fullname)
  #   self.assertEqual([], results, results[0].output)

  def check_test_results(self, results):
    self.assertEqual(2, len(results))
    results.sort(key=lambda result: result['fullname'])
    fail = results[0]
    self.assertEqual(self.test_class_name + '.test_fail', fail['fullname'])
    self.assertEqual([], fail['errors'])
    self.assertEqual(1, len(fail['failures']))
    pas = results[1]
    self.assertEqual(self.test_class_name + '.test_pass', pas['fullname'])
    self.assertEqual([], pas['errors'])
    self.assertEqual([], pas['failures'])

  # acceptable name - pylint:disable-msg=C0103
  def test_test_module_with_one_test_case(self):
    self.config.parallelize_classes = True
    self.config.parallelize_methods = True
    results = self.run_tests(self.module_name)
    self.check_test_results(results)

  def test_test_case(self):
    self.config.parallelize_classes = True
    self.config.parallelize_methods = True
    results = self.run_tests(self.test_class_name)
    self.check_test_results(results)

  def test_test_method(self):
    fullname = self.test_method_name
    results = self.run_tests(fullname)
    self.assertEqual(1, len(results))
    data = results[0]
    self.assertEqual(fullname, data['fullname'])
    self.assertEqual([], data['errors'])
    self.assertEqual([], data['failures'])

  def test_module_fixture(self):
    # Run an in-appserver test that checks module fixtures are used.
    fullname = self.test_package_name + '.test_module_fixture'
    results = self.run_tests(fullname)
    self.assertEqual(1, len(results))
    data = results[0]
    self.assertEqual([], data['errors'])
    self.assertEqual([], data['failures'])

  def test_test_module_with_test_functions(self):
    fullname = self.test_package_name + '.test_test_functions'
    results = self.run_tests(fullname)
    self.assertEqual(1, len(results))
    data = results[0]
    self.assertEqual(fullname, data['fullname'])
    self.assertEqual([], data['errors'])
    self.assertEqual(1, len(data['failures']))

  def test_test_case_with_test_functions(self):
    class_name = 'TestTestFunctionsWrappedTestFunctions'
    fullname = ('%s.test_test_functions.%s' %
                (self.test_package_name, class_name))
    results = self.run_tests(fullname)
    self.assertEqual(1, len(results))
    data = results[0]
    self.assertEqual(fullname, data['fullname'])
    self.assertEqual([], data['errors'])
    self.assertEqual(1, len(data['failures']))

  def test_test_method_with_test_functions(self):
    class_name = 'TestTestFunctionsWrappedTestFunctions'
    fullname = ('%s.test_test_functions.%s.test_pass' %
                (self.test_package_name, class_name))
    results = self.run_tests(fullname)
    self.assertEqual(1, len(results))
    data = results[0]
    self.assertEqual(fullname, data['fullname'])
    self.assertEqual([], data['errors'])
    self.assertEqual([], data['failures'])

  def test_class_fixture(self):
    self.config.parallelize_classes = self.config.parallelize_methods = True
    fullname = self.test_package_name + '.test_class_fixture'
    results = self.run_tests(fullname)
    self.assertEqual(3, len(results))
    results.sort(key=lambda result: result['fullname'])
    self.assertEqual(fullname + '.HasClassFixture', results[0]['fullname'])
    self.assertEqual([], results[0]['errors'])
    self.assertEqual(1, len(results[0]['failures']))
    self.assertEqual(fullname + '.HasNoClassFixture.test_fail',
                     results[1]['fullname'])
    self.assertEqual([], results[1]['errors'])
    self.assertEqual(1, len(results[1]['failures']))
    self.assertEqual(fullname + '.HasNoClassFixture.test_pass',
                     results[2]['fullname'])
    self.assertEqual([], results[2]['errors'])
    self.assertEqual([], results[2]['failures'])
