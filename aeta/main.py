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

"""Entry point to aeta."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

import os.path

from google.appengine.api import users
from google.appengine.ext import webapp
from google.appengine.ext.appstats import recording
from google.appengine.ext.appstats import ui
from google.appengine.ext.webapp import util

from aeta import config
from aeta import handlers
from aeta import rest
from aeta import task_deferred


# short enough, no docstring needed - pylint: disable-msg=C0111
def get_url_mapping():
  conf = config.get_config()
  url_mapping = [(conf.url_path_static + '(.*)',
                  handlers.StaticFileRequestHandler),
                 ]
  url_mapping.extend(rest.get_handler_mapping(conf.url_path_rest))
  url_mapping.append((conf.url_path_deferred, task_deferred.DeferredHandler))
  if conf.use_appstats:
    url_mapping.extend([(os.path.join(conf.url_path, 'stats', path), handler)
                        for (path, handler) in ui.URLMAP])
  # config attributes dynamically assigned - pylint:disable-msg=E1101
  url_mapping.append((conf.url_path + '(.*)', handlers.DefaultRequestHandler))
  return url_mapping


class AuthWsgiMiddleware(object):
  """WSGI middleware to check for authentication."""

  def __init__(self, app):
    """Initializes the WSGI middleware.

    Args:
      app: The WSGI application to wrap.
    """
    self.app = app

  def _user_has_permission(self, environ):
    """Determines if the current user has permission to access aeta tests.

    Args:
      environ: A dictionary of WSGI environment variables.

    Returns:
      A boolean, True iff the user has permission to access aeta.  The user has
      permission iff any of these is true:
      - this is a development server
      - the "user" is the task queue running a task
      - "protected: false" in aeta.yaml
      - the user is an admin or in permitted_emails in aeta.yaml
    """
    if environ.get('SERVER_SOFTWARE', '').startswith('Dev'):
      # Development server.
      return True
    if environ.get('HTTP_X_APPENGINE_TASKNAME'):
      # This variable is set when we are in the task queue.
      return True
    conf = config.get_config()
    if not conf.protected:
      return True
    if users.is_current_user_admin():
      return True
    user = users.get_current_user()
    if user and user.email() in conf.permitted_emails:
      return True
    return False

  def __call__(self, environ, start_response):
    """Standard WSGI function.

    This will run the original WSGI application if the user has permission to
    access aeta, or redirect to a login page otherwise.

    Args:
      environ: Standard WSGI environment dictionary.
      start_response: Standard WSGI function to specify status and headers.

    Returns:
      Standard WSGI iterable of strings for the content.
    """
    if self._user_has_permission(environ):
      return self.app(environ, start_response)
    # Redirect to a login page.
    login_url = users.create_login_url(environ.get('PATH_INFO', ''))
    start_response('302 Found', [('Location', login_url),
                                 ('Content-Type', 'text/html')])
    return []


# The app object is used in a Python 2.7 runtime.
APP = AuthWsgiMiddleware(webapp.WSGIApplication(get_url_mapping()))

if config.get_config().use_appstats:
  # Add appstats, with better stack traces.  This is awkward because the config
  # should be in appengine_config.py, which we do not have access to.
  recording.config.MAX_STACK = 30
  APP = recording.appstats_wsgi_middleware(APP)

# In a Python 2.5 environment, run this as a CGI script.
if __name__ == '__main__':
  util.run_wsgi_app(APP)
