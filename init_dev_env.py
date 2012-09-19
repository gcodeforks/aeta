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

# This script is called by init-dev-env.sh to do Python setup.  Do not run this
# script directly.

import os
import sys

if not os.getenv('DOING_INIT_DEV_ENV'):
  print >> sys.stderr, ('Run init-dev-env.sh instead of running '
                        'init_dev_env.py directly.')
  sys.exit(1)

def try_import(name):
  """Attempts to import a module, reporting an error message otherwise.

  Args:
    name: The name of the module to import.

  Returns:
    The imported module.
  """
  try:
    return __import__(name)
  except ImportError:
    msg = ('Required module %s is not installed.\n' % name +
           'Use "pip install %s" to install it.' % name)
    print >> sys.stderr, msg


unittest2 = try_import('unittest2')
gaedriver = try_import('gaedriver')
webtest = try_import('webtest')
if not (unittest2 and gaedriver and webtest):
  sys.exit(1)

# Find directory of webtest package.
webtest_dir, init = os.path.split(webtest.__file__)
if init not in ['__init__.py', '__init__.pyc']:
  print >> sys.stderr, ('Webtest was found at invalid location %s' %
                        webtest.__file__)

# Create symbolic links to this package so e2e apps can use webtest.
webtest_dir = os.path.abspath(webtest_dir)
for app in ['25', '27']:
  os.system('ln -snf %s testdata/e2e_%s_app/webtest' % (webtest_dir, app))
  os.system('ln -snf %s testdata/e2e_%s_app/webtest' % (webtest_dir, app))


