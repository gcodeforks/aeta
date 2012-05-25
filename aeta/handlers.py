# Copyright 2013 Google Inc. All Rights Reserved.

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

__author__ = 'schuppe@google.com (Robert Schuppenies)'

import cgi
import os

from google.appengine.ext import webapp
from google.appengine.ext.webapp import template

from aeta import config
from aeta import logic


# Django 1.0 and higher autoescapes variables in templates by default,
# before, it did not. Therefore we need to treat different Django
# versions differently for certain output. Luckily, we do not need to
# do this in the templates, but can handle it with some code, that is
# the 'mark_safe' function. If it can be imported, we know we are
# dealing with Django 1.0 or higher, so we disable autoescape for
# certain values. If it cannot be imported we just leave it alone.
try:
  # pylint:disable-msg=F0401
  from django.utils.safestring import mark_safe
except ImportError:
  # pylint:disable-msg=C0103
  mark_safe = None


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
    if not isinstance(msg, str):
      raise TypeError('"msg" must be a string, not a %s' % type(msg))
    if not isinstance(status, (int, long)):
      raise TypeError('"status" must be an int or long, not a %s' %
                      type(status))
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
    if not isinstance(template_file, str):
      raise TypeError('"template_file" must a string, not a %s' %
                      type(template_file))
    if not isinstance(values, dict):
      raise TypeError('"values" must be a dict, not a %s' % type(values))
    if 'title' not in values:
      values['title'] = os.environ['APPLICATION_ID']
    self.response.out.write(template.render(template_file, values))

class DefaultRequestHandler(BaseRequestHandler):
  """Default Request Handler for index and unkown pages."""

  def get(self):
    """Default view."""
    conf = config.get_config()
    errors = []
    modules = []
    # 'test_package_names' is an attribute of conf - pylint:disable-msg=E1101
    for testname in conf.test_package_names:
      # 'test_module_pattern' is an attribute of conf -
      # pylint:disable-msg=E1101
      modules.extend(logic.load_modules(testname, errors,
                                        conf.test_module_pattern))
    moduledata = logic.create_module_data(modules, errors)
    moduledata.sort(key=lambda x: x.fullname)
    values = {'automatic_url': conf.url_path_automatic,
              'moduledata': moduledata,
              'importcheck_url': conf.url_path_importcheck,
              'import_errors': errors,
             }
    self.render_page(_get_template_path('index.html'), values)


class ImportCheckRequestHandler(BaseRequestHandler):
  """Request Handler to check wether a particular module can be imported."""

  # conscious change in argument count - pylint:disable-msg=W0221
  def get(self, fullname):
    """Handle get requests.

    Args:
      fullname: Name of the test object, e.g., the package or module name.
    """
    conf = config.get_config()
    errors = []
    # if fullname describes a package, load modules from path
    path = logic.get_abs_path_from_package_name(fullname)
    if path is None:
      module = logic.load_module_from_module_name(fullname, errors)
      if module:
        modules = [module]
      else:
        modules = []
    else:
      modules = logic.load_modules(fullname, errors,
                                   # 'test_module_pattern' is an attribute of
                                   # conf - pylint:disable-msg=E1101
                                   module_pattern=conf.test_module_pattern)
    moduledata = logic.create_module_data(modules, errors)
    values = {'title': 'Import Checks',
              'moduledata': moduledata,
             }
    self.render_page(_get_template_path('importcheck.html'), values)


class AutomaticTestsRequestHandler(BaseRequestHandler):
  """Request Handler for automatic tests."""

  # conscious change in argument count - pylint:disable-msg=W0221
  def get(self, fullname):
    """View for test results.

    If fullname is empty, all defined tests will be executed.

    Args:
      fullname: Name of the test object, e.g., the package or module name.
    """
    conf = config.get_config()
    fullname = fullname.strip()
    results = []
    if not fullname:
      # 'test_package_names' is an attribute of conf - pylint:disable-msg=E1101
      for testname in conf.test_package_names:
        # 'test_module_pattern' is an attribute of conf -
        # pylint:disable-msg=E1101
        results.extend(logic.load_and_run_tests(testname,
                                                conf.test_module_pattern))
    else:
      # 'test_module_pattern' is an attribute of conf -
      # pylint:disable-msg=E1101
      results = logic.load_and_run_tests(fullname, conf.test_module_pattern)
    for result in results:
      result.output = cgi.escape(result.output)
    if not results:
      return self.render_error("no tests found at '%s'" % fullname, 404)
    values = {'title': 'Automatic Tests',
              'path_to_page': self.request.path,
              'path_to_automatic': conf.url_path_automatic,
              'testresults': results,
              'len_testresults': len(results),
              'empty': '',
             }
    # turn of autoescape in template, if Django 1.0 or higher
    if mark_safe:
      for result in values['testresults']:
        mark_safe(result.output)
    self.render_page(_get_template_path('results.html'), values)
