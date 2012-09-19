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

"""Test utilities."""



import os
import sys

try:
  import json
except ImportError:
  import simplejson as json

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

  def check_response(self, response, expected_content,
                     exact=True, is_json=False):
    """Check a response.

    Args:
      response: A response object.
      expected_status: The expected status code.
      expected_content: The expected content in the response.
      exact: True, if content should match exactly.
      is_json: True, if the expected_content is a JSON object that the response
          should be compared to.
    """
    if hasattr(response, 'body'):
      result_out = response.body
    else:
      response.out.seek(0)
      result_out = response.out.read()
    if exact:
      if is_json:
        result_out = json.loads(result_out)
      # Convert expected_content to JSON and back to handle unicode.
      self.assertEqual(json.loads(json.dumps(expected_content)), result_out)
    else:
      self.assertTrue(result_out.find(expected_content) > -1)


class MockAttributeMixin(object):
  """Used to mock object attributes.

  Usage:

    class SomeTestCase(unittest.TestCase, utils.MockAttributeMixin):

      def setUp(self):
        # Mock deferred.defer
        @self.mock(deferred)
        def defer(func, *args, **kwargs):
          ...

        # Mock config.get_config
        @self.mock(config)
        def get_config():
          ...

      def tearDown(self):
        self.tear_down_attributes()
    """

  def mock(self, obj, attr_name=None):
    """Mocks an attribute of an object.

    This will set the given attribute of the object to the value passed in and
    save the original value of the attribute.  The original value will be
    restored when tear_down_attributes() is called.

    This function has 2 usage patterns:

    To mock functions, methods, or classes:

    @self.mock(object_containing_attribute)
    def function_name(arguments):  # alternatively: class class_name
      ...

    To mock other objects:
    self.mock(object_containing_attribute, 'attribute_name')(new_value)

    Args:
      obj: The object whose attribute should be mocked.  This is usually a
          module or class but may be any object with mutable attributes.
      attr_name: The name of the attribute.  This is only required if the new
          attribute value does not have __name__ defined.

    Returns:
      A wrapper function for the mock value.
    """

    def wrapper(new_value):
      """Wrapper for the new attribute value.

      Args:
        new_value: The mock value that the attribute will be set to for the
            duration of the test.
      """
      name = attr_name or new_value.__name__
      old_value = getattr(obj, name)
      if not hasattr(self, 'old_mock_attributes'):
        self.old_mock_attributes = []
      self.old_mock_attributes.append((obj, name, old_value))
      setattr(obj, name, new_value)
    return wrapper

  def tear_down_attributes(self):
    """Restores all mocked objects' attributes to their original values.

    This should be called in tearDown().
    """
    # Treat old_mock_attributes as a stack to handle cases where the same
    # property is mocked twice.
    while getattr(self, 'old_mock_attributes', False):
      (obj, name, old_value) = self.old_mock_attributes.pop()
      setattr(obj, name, old_value)



