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

"""Models used by aeta."""

from __future__ import with_statement



# Classes defined here are only data containers - pylint:disable-msg=R0903

import logging
import unittest


from google.appengine.api import files
from google.appengine.ext import blobstore
from google.appengine.ext import ndb

try:
  import json
except ImportError:
  import simplejson as json

from aeta import task_deferred as deferred
from aeta import utils

__all__ = ['TestBatch', 'RunTestUnitTask', 'get_ctx_options']


# The maximum size of a JSON object in a JsonHolder.  Since memcache and the
# datastore both have a maximum of 1MB, the object must be a bit smaller than
# 1MB.
_MAX_JSON_BYTES = 1024 * 1000

# How long to wait between attempts to delete dead blobs.
_DELETE_BLOB_TIME_SECS = 10 * 60


class JsonHolder(ndb.Model):
  """A superclass for models that hold a potentially large JSON object.

  The object will either be stored in the model or in the Blobstore depending
  on its size.

  Attributes:
    data: The text of the JSON, or None if JSON has not been set or it is it
        the Blobstore.
    blob_key: A BlobKey to the JSON text stored in the Blobstore, or None if no
        data is stored in the Blobstore.
  """

  data = ndb.TextProperty(default=None)
  blob_key = ndb.BlobKeyProperty(default=None)

  def set_json(self, json_obj, conf):
    """Sets the JSON value of this object.

    If the JSON value is stored in the Blobstore, a task will be added to
    eventually delete the blob.

    Note that you also have to put() the model after calling this function to
    actually update it.

    Args:
      json_obj: The JSON-convertible object to set.
      conf: The configuration to use.

    Raises:
      ValueError: If this object does not have a key.
    """
    if not self.key:
      raise ValueError("Set the object's key before calling set_json().")
    data = json.dumps(json_obj)
    if len(data) <= _MAX_JSON_BYTES:
      self.data = data
    else:
      self.data = None
      file_name = files.blobstore.create()
      with files.open(file_name, 'a') as f:
        f.write(data)
      files.finalize(file_name)
      self.blob_key = files.blobstore.get_blob_key(file_name)
      deferred.defer(_delete_blob_if_done, self.key, self.blob_key, conf,
                     _queue=conf.test_queue, _countdown=_DELETE_BLOB_TIME_SECS)

  def get_json(self):
    """Gets the JSON value of this object.

    Returns:
      The JSON object that was set.
    """
    json_obj = None
    if self.data is not None:
      json_obj = json.loads(self.data)
    elif self.blob_key:
      info = blobstore.BlobInfo.get(self.blob_key)
      if info:
        f = info.open()
        json_obj = json.loads(f.read())
        f.close()
    return json_obj


class TestBatch(JsonHolder):
  """A collection of tests to be run at once.

  JSON data is of the following form:
  {'fullname': the full name of the test object,
   'load_errors': a list of [object name, error string] for load errors,
   'test_unit_method': a mapping from test unit name to a list of method
       fullnames  in that test object
  }
  or None if the batch has not been initialized.

  Attributes:
    fullname: The name of the object the tests are being run for.  This should
        be a period-separated name of a Python test package, module, class, or
        method, or the empty string if all tests are being run.
    num_units: How many testing units this batch consists of.  There will be
        one RunTestUnitTask per unit.  This will be None if the number of units
        is not yet known.
  """
  fullname = ndb.StringProperty()
  num_units = ndb.IntegerProperty(default=None)

  def get_tasks(self, conf):
    """Get all RunTestUnitTasks associated with the TestBatch.

    Args:
      conf: The configuration to use.

    Returns:
      A list of RunTestUnitTasks associated with this TestBatch, or None if the
      tasks have not yet been initialized.
    """
    if self.num_units is None:
      return None
    keys = []
    for i in range(self.num_units):
      keys.append(RunTestUnitTask.get_key(self.key, i))
    return ndb.get_multi(keys, **get_ctx_options(conf))

  def set_info(self, load_errors, test_unit_methods, conf):
    """Sets batch information.

    This information can be retrieved as JSON using get_json().

    Args:
      load_errors: A list of (object name, error string) pairs for load errors.
      test_unit_methods: A mapping from test unit fullname to a list of method
          fullnames in that object.
      conf: The configuration to use.
    """
    utils.check_type(load_errors, 'load_errors', list)
    utils.check_type(test_unit_methods, 'test_unit_methods', dict)
    data = {'num_units': self.num_units,
            'load_errors': load_errors,
            'test_unit_methods': test_unit_methods,
           }
    self.set_json(data, conf)


class RunTestUnitTask(JsonHolder):
  """The state of a task that runs a single TestSuite in a batch of them.

  When creating a new RunTestUnitTask, always set its key to the return value
  of get_key.  This enables easy access to RunTestUnitTasks given their batch.

  JSON data should be of the form returned by get_test_result_json(), or None
  if the test has not finished running.

  Attributes:
    fullname: The full name to the TestSuite being run.
  """
  fullname = ndb.StringProperty()

  @classmethod
  def get_key(cls, batch_key, index):
    """Gets the key associated with a RunTestUnitTask.

    Args:
      batch_key: The key to the TestBatch the RunTestUnitTask is part of.
      index: The integer index assigned to the task, which is in the range
          [0, batch.num_units).

    Returns:
      A ndb.Key instance corresponding to the RunTestUnitTask.
    """
    utils.check_type(batch_key, 'batch_key', ndb.Key)
    utils.check_type(index, 'index', int)
    return ndb.Key(cls, str(index), parent=batch_key)

  def set_test_result(self, load_errors, testresult, output, conf):
    """Sets test result information.

    This information can be retrieved as JSON using get_json().

    Args:
      load_errors: A list of (object name, error string) pairs for load errors.
      testresult: The unittest.TestResult for this test run.
      output: The output of print statements in the test.
      conf: The configuration to use.
    """
    utils.check_type(load_errors, 'load_errors', list)
    utils.check_type(testresult, 'testresult', unittest.TestResult)
    utils.check_type(output, 'output', basestring)

    data = {
        'fullname': self.fullname,
        'load_errors': load_errors,
        'errors': [(tc.fullname, exc) for (tc, exc) in testresult.errors],
        'failures': [(tc.fullname, exc) for (tc, exc) in testresult.failures],
        'output': output,
    }
    self.set_json(data, conf)


def get_ctx_options(conf):
  """Gets the appropriate context options for storing test information.

  These context options are passed as keyword arguments to methods including
  ndb.Key.get(), ndb.Key.put(), ndb.get_multi(), and ndb.put_multi() to control
  how various storage methods are used.

  Args:
    conf: The configuration to use.  Its storage specifies how results
        should be stored.

  Returns:
    A dictionary of keyword arguments.
  """
  method = conf.storage
  if method == 'datastore':
    return {}
  if method == 'memcache':
    return {'use_memcache': True, 'use_datastore': False}
  if method == 'immediate':
    return {'use_cache': True, 'use_memcache': False, 'use_datastore': False}
  logging.warning('[aeta] Unknown run method %s.  Falling back to memcache.',
                  method)
  return {'use_memcache': True, 'use_datastore': False}


def _delete_blob_if_done(obj_key, blob_key, conf):
  """Deletes a blob if its object has also been deleted.

  Otherwise, it will try to delete the blob later.

  Args:
    obj_key: The ndb.Key of a JsonHolder.
    blob_key: The BlobKey to delete.
    conf: The configuration to use.
  """
  if obj_key.get(**get_ctx_options(conf)):
    deferred.defer(_delete_blob_if_done, obj_key, blob_key, conf,
                   _queue=conf.test_queue, _countdown=_DELETE_BLOB_TIME_SECS)
  else:
    info = blobstore.BlobInfo.get(blob_key)
    if info:
      info.delete()


