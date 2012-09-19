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

"""Basic handlers for aeta."""



import cgi
import os
import urllib

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from aeta import config
from aeta import logic
from aeta import utils


__all__ = ['BaseRequestHandler', 'DefaultRequestHandler',
           'ImportCheckRequestHandler', 'AutomaticTestsRequestHandler']

_TEMPLATES_PATH = os.path.join(os.path.dirname(__file__), 'templates')


def _get_template_path(name):
  """Get path to a template with the given name.

  This method was introduced mainly to make testing easier.
  """
  return os.path.join(_TEMPLATES_PATH, name)


class BaseRequestHandler(webapp.RequestHandler):
  """Base class to all Request Handlers."""

  def render_error(self, msg, status):
    """Render msg into an error page and write result to self.response.

    Args:
      msg: The error message presented to the user.
      status: HTTP status code of the error.

    Raises:
      ValueError: Wrong input arguments.
    """
    if isinstance(msg, unicode):
      msg = msg.encode('utf-8')
    utils.check_type(msg, 'msg', str)
    utils.check_type(status, 'status', (int, long))
    self.response.out.write(template.render(_get_template_path('error.html'),
                                            {'message': msg}))
    self.response.set_status(status)

  def render_page(self, template_file, values):
    """Render values into template_file and write result to self.response.

    Args:
      template_file: The filename of the template file to use.
      values: A dictionary of template variable names and values.

    Raises:
      ValueError: Wrong input arguments.
    """
    utils.check_type(template_file, 'template_file', str)
    utils.check_type(values, 'values', dict)
    if 'title' not in values:
      values['title'] = os.environ['APPLICATION_ID']
    self.response.out.write(template.render(template_file, values))


class DefaultRequestHandler(BaseRequestHandler):
  """Default Request Handler for index and unkown pages."""

  def get(self, fullname):
    """Default view."""
    conf = config.get_config()
    obj = logic.get_requested_object(fullname, conf)
    if isinstance(obj, logic.BadTest):
      if obj.exists:
        self.render_error('Error loading test object %s: \n%s' %
                          (fullname, obj.load_errors[0][1]), 500)
      else:
        self.render_error('Test object %s does not exist.' % fullname, 404)
      return
    # urllib.quote is necessary for things embedded in <script> tags to avoid
    # things like quotes and </script> in the string literals.
    values = {'root_name': urllib.quote(fullname),
              'rest_path': urllib.quote(conf.url_path_rest),
              'static_path': conf.url_path_static,
             }
    self.render_page(_get_template_path('index.html'), values)


class StaticFileRequestHandler(BaseRequestHandler):
  """Request Handler for static files."""

  # A mapping from file name (the part after /static/) to file contents.
  # This is a class variable because new RequestHandlers are created for each
  # request.
  _file_cache = {}

  # conscious change in argument count - pylint:disable-msg=W0221
  def get(self, name):
    """Gets the contents of a static file.

    Args:
      name: Name of the static file.
    """
    if name.endswith('.js'):
      self.response.headers['Content-Type'] = 'text/javascript'
    if name in StaticFileRequestHandler._file_cache:
      self.response.out.write(StaticFileRequestHandler._file_cache[name])
      return
    file_name = '%s/static/%s' % (os.path.dirname(__file__), name)
    try:
      f = open(file_name, 'r')
      content = f.read()
      f.close()
    except IOError:
      self.render_error('File not found.', 404)
      return
    StaticFileRequestHandler._file_cache[name] = content
    self.response.out.write(content)
