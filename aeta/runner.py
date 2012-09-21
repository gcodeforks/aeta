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

"""Runs tests in the task queue.

Operation:
1.  start_batch is called.  A TestBatch is created, and one RunTestUnitTask
    is created for every unit in the batch.
2.  wait_for_results is called.  This will wait for all tests to run.
3.  The tasks are run in the task queue.  Each task runs a test unit and
    stores the result back in the RunTestUnitTask (in the datastore).
4.  When all tasks are finished, wait_for_results returns them and the caller
    can use the results.
5.  If no progress has been made on a test batch (no additional tests run)
    for a long time, the entire batch and all tasks are deleted to conserve
    memory.
"""

__author__ = 'jacobltaylor@gmail.com (Jacob Taylor)'

import logging
import os
import StringIO
import sys
import time
import unittest

from google.appengine.ext import ndb

from aeta import config
from aeta import logic
from aeta import models
from aeta import task_deferred as deferred
from aeta import utils


# How long to wait between attempts to delete the batch and tasks.  The batch
# and tasks will almost certainly not be deleted unless this amount of time
# passes without any more tests finishing (because all have completed or
# because one times/errors out).
_DELETE_TIME_SECS = 30 * 60


def _run_test_and_capture_output(test):
  """Run a test and capture the printed output.

  By default, the unittest framework only writes test related data to the given
  stream and ignores other output, e.g., from print statements. This function
  wraps the test execution and captures only the printed output.

  Args:
    test: The test to run (can be a TestSuite or a TestCase).

  Returns:
    A (testresult, output) tuple. 'testresult' is the return value of
    the TestRunner, 'output' the print output emitted during the test run.

  Raises:
    TypeError: Wrong input arguments.
  """
  utils.check_type(test, 'test', (unittest.TestSuite, unittest.TestCase))
  output = StringIO.StringIO()
  original_stdout = sys.stdout
  original_stderr = sys.stderr
  sys.stdout = output
  sys.stderr = output
  try:
    # Ignore output from unittest.
    runner = unittest.TextTestRunner(stream=StringIO.StringIO(), verbosity=2)
    testresult = runner.run(test)
  finally:
    sys.stdout = original_stdout
    sys.stderr = original_stderr
  return testresult, output.getvalue()


def _this_task_has_failed_before():
  """Determines if the current task has failed before.

  Returns:
    True if this code is executing in a task that failed before and is
        retrying, False otherwise.
  """
  return int(os.environ.get('X-AppEngine-TaskRetryCount', '0')) > 0


def _run_test_unit(fullname, task_key, conf):
  """Runs a single test unit based on a RunTestUnitTask.

  The test identified by the task is run and the result is stored in the
  RunTestUnitTask.

  Args:
    fullname: The full name of the test unit to run.
    task_key: The key of the RunTestUnitTask to run.
    conf: The configuration to use.
  """
  ctx_options = models.get_ctx_options(conf)
  task = models.RunTestUnitTask(key=task_key, fullname=fullname)
  load_errors = []
  if _this_task_has_failed_before():
    # This will appear to the user as a "load error" in the test.
    msg = 'Unknown error running test %s.  See log for details.' % fullname
    load_errors.append((fullname, msg))
    try:
      task.set_test_result(load_errors, unittest.TestResult(), '', conf)
      task.put(**ctx_options)
    # pylint: disable-msg=W0703
    except:
      msg = 'Error writing message about the test %s that failed!' % fullname
      logging.exception(msg)
    return
  test = logic.get_requested_object(fullname, conf)
  suite = test.get_suite(conf, load_errors)
  # Since the test is a TestSuite, its run method will handle all the
  # administrative work involved in setUpModule, setUpClass, skipping, etc.
  result, output = _run_test_and_capture_output(suite)
  task.set_test_result(load_errors, result, output, conf)
  task.put(**ctx_options)


def _delete_batch(batch_key, prev_done, conf):
  """Deletes the given batch and its tasks if no progress has been made.

  Otherwise, it will check back in _DELETE_TIME_SECS seconds.

  Note that any blobs used in this batch will eventually be deleted after their
  respective TestBatch/RunTestUnitTask objects are deleted; see
  models._delete_blob_if_done().

  Args:
    batch_key: The key to the TestBatch to delete.
    prev_done: How many tests were done _DELETE_TIME_SECS seconds ago.  If the
        number of completed tests has not increased, the batch is deleted.
    conf: The configuration to use.
  """
  ctx_options = models.get_ctx_options(conf)
  batch = batch_key.get(**ctx_options)
  if batch is None: return  # For idempotency.
  utils.check_type(batch, 'batch', models.TestBatch)
  tasks = [task for task in batch.get_tasks(conf) if task]
  num_done = len(tasks)
  if num_done == prev_done:
    task_keys = [task.key for task in tasks]
    ndb.delete_multi([batch_key] + task_keys, **ctx_options)
  else:
    deferred.defer(_delete_batch, batch_key, num_done, conf,
                   _queue=conf.test_queue, _countdown=_DELETE_TIME_SECS)


def _initialize_batch(fullname, batch_key, conf):
  """Initializes a TestBatch to start the tests running.

  This function creates a RunTestUnitTask for every test unit in the batch and
  starts running them in the background.

  Args:
    batch_key: The ndb.Key of the batch to initialize.
    conf: The configuration to use.
    run_immediately: If set to True, tests will be run immediately rather than
        in the task queue.  They will be finished before this function returns.
  """
  ctx_options = models.get_ctx_options(conf)
  errors_out = []
  batch = models.TestBatch(key=batch_key, fullname=fullname)
  if _this_task_has_failed_before():
    # This will appear to the user as a "load error" in the batch.
    msg = ('Unknown error initializing batch %s.  See log for details.' %
           fullname)
    errors_out.append((fullname, msg))
    try:
      batch.set_info(errors_out, {}, conf)
      batch.put(**ctx_options)
    # pylint: disable-msg=W0703
    except:
      msg = 'Error writing message about the batch %s that failed!' % fullname
      logging.exception(msg)
    return
  test = logic.get_requested_object(fullname, conf)
  test_units = test.get_units(conf, errors_out)
  test_unit_methods = {}
  tasks = []
  defer_calls = []
  for (i, unit) in enumerate(test_units):
    # Ignore loading errors for now.  _run_test_unit will detect loading errors
    # when its task is executed.
    method_names = [method.fullname for method in unit.get_methods(conf)]
    test_unit_methods[unit.fullname] = method_names
    task_key = models.RunTestUnitTask.get_key(batch_key, i)
    tasks.append(models.RunTestUnitTask(key=task_key, fullname=unit.fullname))
  batch.set_info(errors_out, test_unit_methods, conf)
  # Put batch after tasks, so that we don't see that the batch has tasks before
  # they exist.
  ndb.put_multi(tasks + [batch], **ctx_options)
  for task in tasks:
    call = deferred.DeferredCall(_run_test_unit, str(task.fullname), task.key,
                                 conf)
    if conf.storage == 'immediate':
      call.run()
    else:
      defer_calls.append(call)
  if ctx_options.get('use_datastore', True):
    defer_calls.append(deferred.DeferredCall(_delete_batch, batch.key, 0, conf,
                                             _countdown=_DELETE_TIME_SECS))
  deferred.defer_multi(defer_calls, queue=conf.test_queue)


def start_batch(fullname, conf):
  """Creates a TestBatch for all the given tests and returns it.

  Eventually, all tests will automatically run in the background.

  Args:
    fullname: The full name of the group of tests to run.  This should be the
        period-separated name of a test package, module, class, or method, or
        the empty string to run all tests.
    conf: The configuration to use.
    run_immediately: If set to True, tests will be run immediately rather than
        in the task queue.  They will be finished before this function returns.

  Returns:
    The TestBatch created for the run.

  Raises:
    TypeError: Wrong input arguments.
  """
  utils.check_type(fullname, 'fullname', str)
  utils.check_type(conf, 'conf', config.Config)
  ctx_options = models.get_ctx_options(conf)
  # It's necessary to set the key because if ctx_options['use_datastore'] ==
  # False, the key will not be set to something reasonable automatically.
  batch_key = ndb.Key(models.TestBatch, utils.rand_unique_id())
  batch = models.TestBatch(fullname=fullname, key=batch_key)
  batch.put(**ctx_options)
  call = deferred.DeferredCall(_initialize_batch, fullname, batch_key, conf)
  if conf.storage == 'immediate':
    call.run()
    # _initialize_batch() should have updated batch data
    return batch.key.get(**ctx_options)
  else:
    deferred.defer_multi([call], queue=conf.test_queue)
    return batch
