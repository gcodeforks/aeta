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

"""Entry point to aeta."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'


from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

from aeta import config
from aeta import handlers
from aeta import rest


# short enough, no docstring needed - pylint: disable-msg=C0111
def get_url_mapping():
  conf = config.get_config()
  url_mapping = [(conf.url_path_importcheck + '(.*)',
                  handlers.ImportCheckRequestHandler),
                 (conf.url_path_automatic + '(.*)',
                  handlers.AutomaticTestsRequestHandler),
                 ]
  url_mapping.extend(rest.get_handler_mapping(conf.url_path_rest))
  # config attributes dynamically assigned - pylint:disable-msg=E1101
  url_mapping.append((conf.url_path + '.*', handlers.DefaultRequestHandler))
  return url_mapping


# The app object is used in a Python 2.7 runtime.
APP = webapp.WSGIApplication(get_url_mapping())

# In a Python 2.5 environment, run this as a CGI script.
if __name__ == '__main__':
  util.run_wsgi_app(APP)
