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

"""Emulates deferred library using the task queue.

This prevents the user from having to configure deferred in app.yaml.
"""

import logging
import os
import pickle

from google.appengine.api import taskqueue
from google.appengine.ext import webapp

from aeta import config

# The queue to put deferred tasks in if no queue is specified.
_DEFAULT_QUEUE = 'default'


class DeferredCall(object):
  """A deferred function call.

  The DeferredCall can be created, pickled, unpickled, then called.

  Attributes:
    func: The function to call.
    countdown: How many seconds to wait before calling the function.
    args: Arguments to pass to func.
    kwargs: Keyword arguments to pass to func.
  """

  def __init__(self, func, *args, **kwargs):
    """Creates a deferred function call.

    Args:
      func: The function to call.
      _countdown: How many seconds to wait before running the task.
      *args: Arguments to pass to func.
      **kwargs: Keyword arguments to pass to func.

    Raises:
      ValueError: func is not callable
    """
    if not hasattr(func, '__call__'):
      raise ValueError('"func" must be callable but is %s' % type(func))
    self.func = func
    self.args = args
    self.countdown = kwargs.pop('_countdown', 0)
    self.kwargs = kwargs

  def run(self):
    """Makes the function call that was deferred."""
    self.func(*self.args, **self.kwargs)


def defer_multi(calls, queue=_DEFAULT_QUEUE):
  """Defers multiple function calls.

  Args:
    calls: A list of DeferredCall objects.
    queue: The queue to run the tasks in.
  """
  url = config.get_config().url_path_deferred
  # Go in batches of MAX_TASKS_PER_ADD to avoid the limit.
  for batch_i in range(0, len(calls), taskqueue.MAX_TASKS_PER_ADD):
    tasks = []
    for call in calls[batch_i : batch_i + taskqueue.MAX_TASKS_PER_ADD]:
      tasks.append(taskqueue.Task(url=url, countdown=call.countdown,
                                  payload=pickle.dumps(call)))
    taskqueue.Queue(queue).add(tasks)


def defer(func, *args, **kwargs):
  """Emulates deferred.defer.

  This is mostly identical to deferred.defer but fewer features are supported.

  Args:
    func: The function to call.
    _queue: The name of the queue to use for this task.
    _countdown: How many seconds to wait before running the task.
    *args: Arguments to pass to func.
    **kwargs: Keyword arguments to pass to func.

  Raises:
    ValueError: func is not callable
  """
  queue = kwargs.pop('_queue', _DEFAULT_QUEUE)
  # DeferredCall() will handle the _countdown keyword argument.
  defer_multi([DeferredCall(func, *args, **kwargs)], queue=queue)


class DeferredHandler(webapp.RequestHandler):
  """Handles requests from the task queue to run deferred tasks."""

  def post(self):
    # Additional protection is required because this handler can execute
    # arbitrary code.  Even if the user sets "protected: false" in aeta.yaml,
    # it should not be possible to call this handler outside the task queue.
    if not os.environ.get('HTTP_X_APPENGINE_TASKNAME'):
      self.response.set_status(403)
      self.response.out.write("aeta's task handler can only be called from "
                              'the task queue.')
      return
    payload = self.request.body
    try:
      call = pickle.loads(payload)
    except Exception:
      # prevent task from being retried
      logging.exception('[aeta] Failed during deferred unpickling.')
      return
    try:
      call.run()
    except Exception:
      logging.exception('[aeta] Failed during deferred task; retrying.')
      raise
