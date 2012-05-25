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

"""Test utilities."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

import os
import sys

TEST_PACKAGE_ROOT = os.path.join('testdata', 'test_modules')


class TestDataMixin(object):
  """Mixin that provides test data for testing."""

  # definition outside __init__ is okay - pylint:disable-msg=W0201
  def setup_test_data(self):
    """Set up test data."""
    # The testdata directory is sibling to the parent directory of this
    # module.
    root_dir = os.path.dirname(os.path.dirname(__file__))
    self._testdata_dir = os.path.join(root_dir, TEST_PACKAGE_ROOT)
    sys.path.append(self._testdata_dir)
    self.test_package_name = 'sample_package'

  def tear_down_test_data(self):
    """Tear down test data."""
    sys.path.remove(self._testdata_dir)


class HandlerTestMixin(object):
  """Mixin for easier handler testing."""

  # a method is fine - pylint:disable-msg=R0201
  def get_response_code(self, response):
    """Get the response code."""
    if os.environ.get('APPENGINE_RUNTIME') == 'python27':
      return response.status_int
    else:
      return response.status

  def check_response(self, response, expected_status, expected_content,
                     exact=True):
    """Check a response.

    Args:
      response: A response object.
      expected_status: The expected status code.
      expected_content: The expected content in the response.
      exact: True, if content should match exactly.
    """
    if os.environ.get('APPENGINE_RUNTIME') == 'python27':
      result_out = self.handler.response.body
      self.assertTrue(result_out.find(expected_content) > -1, result_out)
    else:
      self.handler.response.out.seek(0)
      result_out = self.handler.response.out.read()
      if exact:
        self.assertEqual(expected_content, result_out)
      else:
        self.assertTrue(result_out.find(expected_content) > -1)
    self.assertEqual(expected_status, self.get_response_code(response))
