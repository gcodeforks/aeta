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

"""REST interface to the App Engine test extension (aeta).

The REST interface will respond to request regarding test objects.  A test
object can be a package, a module, a class, or a test method. The name pattern
used is similar to the standard Python pattern which describes a hierarchy such
as package.subpackage.module.class.method.  The name can also be an empty
string to indicate that all tests should be run.

The interface has the following top level paths:
- start_batch/<fullname>
- batch_info/<batch id>
- batch_results/<batch id>?start=<integer>

For the start_batch request, a full object name (according to the pattern
described above) is expected to follow the top level path.  Other requests
expect a batch id which is returned by start_batch.  All requests will respond
with a JSON object or an HTTP error, e.g. if a particular object could not be
found.


Get methods
---------------

Usage:
  POST /tests/rest/get_methods/some.test

This will get a list of test methods contained in some test object.  If no test
name is given, it will return all test methods.  The response will be JSON in
the following format:
{'method_names': A list of test method full names.
 'load_errors': A list of errors that were encountered while trying to get the
                test units contained in the batch.  Each error is of the form
                [object fullname, exception string].
}


Start batch
---------------

Usage:
  POST /tests/rest/start_batch/some.test

This will start running the test batch in the background.  The test batch
will run all tests named by the part of the URL after start_batch/.  If no
test name is given, it will run all tests named in the application's
test_package_names configuration.

The response will be the numeric ID of the test batch.


Batch info
---------------

Usage:
  GET /tests/rest/batch_info/2451515

This will get data regarding the batch identified by the given number.  The
response will be JSON in the following format:

{'num_units': The number of testing units in the batch, or null if this number
              is not currently known.
 'test_unit_methods': A dictionary mapping test unit fullname to a list of test
                      method full names contained in that test unit.  All test
                      units that are part of the batch will be returned.  If
                      these are not yet known, then test_unit_methods will be
                      null.  This gives the local client enough information to
                      create the local test suites.
 'load_errors': A list of errors that were encountered while trying to get the
                test units contained in the batch.  Each error is of the form
                [object fullname, exception string].
}


Batch results
---------------

Usage:
  GET /tests/rest/batch_results/364?start=5

This retrieves and returns a list of test results for test units that have
completed.  Which results are returned depends on both which tests have
completed and the start argument.  'start' should be an index into the list of
test units.  The results returned consist of the results of units starting at
this index and extending up to the final completed result in this stretch.  For
example, if tests 0, 1, 2, 3, and 5 have completed, and the start argument is
1, then results 1, 2, and 3 will be returned.  This protocol makes it easy for
the caller to make repeated calls to gradually get all test results in order.

The response will be JSON in the following format:

[{'fullname': full name of the test unit,
  'load_errors': An array of [object name, error traceback] arrays of any load
                 errors encountered while loading the tests in this unit.
  'errors': An array of [test method name, error traceback] arrays of all test
            methods that caused an error,
  'failures': An array of [test method name, error traceback] arrays of all
              test methods which failed,
  'output': Output of the entire test run,
 }]
"""

__author__ = 'schuppe@google.com (Robert Schuppenies)'



from google.appengine.ext import ndb
try:
  # Location when on the app server
  from google.appengine.runtime import DeadlineExceededError
except ImportError:
  # Location when on the development server
  from google.appengine.runtime.apiproxy_errors import DeadlineExceededError

try:
  import json
except ImportError:
  import simplejson as json

from aeta import utils
from aeta import config
from aeta import logic
from aeta import handlers
from aeta import models
from aeta import runner


_MEMCACHE_FAILURE_MESSAGE = ('Try again later, or consider setting "storage" '
                             'in aeta.yaml to "datastore" instead.')


class Error(Exception):
  """Base rest error type."""


class IncorrectUsageError(Error):
  """Raised when the REST API is used incorrectly."""
  pass


class MemcacheFailureError(Error):
  """Raised when data is unavailable due to memcache failure."""


def get_batch_results(batch, start):
  """Gets new test results from a batch.

  Args:
    batch: The models.TestBatch instance whose tests to get.
    start: The lowest index of the test result to return.

  Returns:
    A list of JSON-converted test result data for all consecutive completed
        tests starting from start.

  Raises:
    MemcacheFailureError: If test results are unavailable due to memcache
        failure.
  """
  utils.check_type(batch, 'batch', models.TestBatch)
  utils.check_type(start, 'start', int)
  tasks = ndb.get_multi([models.RunTestUnitTask.get_key(batch.key, i)
                         for i in range(start, batch.num_units)])
  results = []
  if batch.num_units is not None:
    for task in tasks:
      if not task:
        raise MemcacheFailureError()
      result = task.get_json()
      if not result:
        break
      results.append(result)
  return results


class BaseRESTRequestHandler(handlers.BaseRequestHandler):
  """Request handler for REST API."""

  def render_error(self, msg, status):
    """Write an error message to self.response.

    Args:
      msg: The content of the response.
      status: The status code of the response.
    """
    self.response.out.write(msg)
    self.response.set_status(status)

  def get_batch(self, batch_id):
    batch = ndb.Key(models.TestBatch, batch_id).get()
    if not batch:
      msg = 'No batch with id %s found.' % batch_id
      if config.get_config().storage == 'memcache':
        msg += ('\nThis could be due to memcache failing.  ' +
                _MEMCACHE_FAILURE_MESSAGE)
      self.render_error(msg, 404)
    return batch


class GetMethodsRequestHandler(BaseRESTRequestHandler):
  """Request handler for getting test methods."""

  def get(self, fullname):
    conf = config.get_config()
    load_errors = []
    test = logic.get_requested_object(fullname, conf)
    methods = test.get_methods(conf, load_errors)
    data = {'method_names': [method.fullname for method in methods],
            'load_errors': load_errors}
    self.response.out.write(json.dumps(data))


class StartBatchRequestHandler(BaseRESTRequestHandler):
  """Request handler for starting a test batch."""

  def post(self, fullname):
    conf = config.get_config()
    obj = logic.get_requested_object(fullname, conf)
    if isinstance(obj, logic.BadTest):
      if obj.exists:
        self.render_error('Error loading test object %s: \n%s' %
                          (fullname, obj.load_errors[0][1]), 500)
      else:
        self.render_error('Test object %s does not exist.' % fullname, 404)
      return
    conf = config.get_config()
    try:
      batch = runner.start_batch(fullname, conf)
    except DeadlineExceededError:
      self.render_error('Tests took too long to run.  Consider setting the '
                        '"storage" option in aeta.yaml to something other '
                        'than "immediate", such as "memcache".', 500)
      return
    if conf.storage == 'immediate':
      tasks = batch.get_tasks(conf)
      data = {'batch_info': batch.get_json(),
              'results': [task.get_json() for task in tasks]
             }
    else:
      data = {'batch_id': str(batch.key.id())}
    self.response.out.write(json.dumps(data))


class BatchInfoRequestHandler(BaseRESTRequestHandler):
  """Request handler for getting general information about a test batch."""

  def get(self, batch_id):
    batch = self.get_batch(batch_id)
    if batch:
      self.response.out.write(json.dumps(batch.get_json()))


class BatchResultsRequestHandler(BaseRESTRequestHandler):
  """Request handler for polling for completed test results in a batch."""

  def get(self, batch_id):
    batch = self.get_batch(batch_id)
    if batch:
      try:
        start = int(self.request.get('start'))
      except ValueError:
        self.render_error('Not an integer: %s' % self.request.get('start'),
                          400)
        return
      if not 0 <= start < (batch.num_units or 1):
        self.render_error('start must be at least 0 and under the number of '
                          'test units (%s) but is %s' %
                          (batch.num_units, start), 400)
        return
      try:
        results = get_batch_results(batch, start)
      except MemcacheFailureError:
        self.render_error('Memcache failed when running tests.  ' +
                          _MEMCACHE_FAILURE_MESSAGE)
      self.response.out.write(json.dumps(results))


def get_handler_mapping(urlprefix):
  """Get mapping of URL prefix to handler."""
  utils.check_type(urlprefix, 'urlprefix', basestring)
  mapping = (('%sget_methods/(.*)' % urlprefix, GetMethodsRequestHandler),
             ('%sstart_batch/(.*)' % urlprefix, StartBatchRequestHandler),
             ('%sbatch_info/(.*)' % urlprefix, BatchInfoRequestHandler),
             ('%sbatch_results/(.*)' % urlprefix, BatchResultsRequestHandler),
            )
  return mapping
