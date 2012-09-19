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

"""Tests for the models module of aeta."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

# Disable checking; pylint: disable-msg=C0111,W0212,R0904,C0103
# - docstrings
# - access to protected members
# - too many public methods
# - setUp() and tearDown() method names

import unittest

from aeta import config


SET_CONFIG_OPTIONS = {'test_package_names': 'tests1, tests2',
                      'test_module_pattern': '^[\w]+_test$',
                      'url_path': '/tests/',
                      }

class ConfigTest(unittest.TestCase):
  """Tests for config.Config."""

  def test_init(self):
    """Test initialization."""
    conf = config.Config()
    for option in SET_CONFIG_OPTIONS:
      self.assertEqual(config.Config.NOT_SET, getattr(conf, option))
    for option in config.Config.COMPUTED_PATH_OPTIONS:
      private_name = '_' + option
      self.assertEqual(config.Config.NOT_SET, getattr(conf, private_name))

  def test_init_with_args(self):
    """Test initialization."""
    self.assertRaises(config.ConfigError, config.Config, a=1)
    conf = config.Config(**SET_CONFIG_OPTIONS)
    for option in SET_CONFIG_OPTIONS:
      value = SET_CONFIG_OPTIONS[option]
      self.assertEqual(value, getattr(conf, option))

  def test_get_path_property(self):
    # We test this using an example option.
    url_path = '/a-test-path/'
    name = 'automatic'
    expected_suffix = config.Config.COMPUTED_PATH_OPTIONS[name]
    expected_value = '/a-test-path/%s/' % expected_suffix
    conf = config.Config()
    conf.url_path = url_path
    self.assertEqual(expected_value, conf._get_path_property(name))
    # Check computed and cached value.
    self.assertEqual(expected_value, conf._automatic)
    # Check cached value is used if available.
    conf._automatic = 'cached_value'
    self.assertEqual('cached_value', conf._get_path_property(name))

  def check_property(self, property_name):
    url_path = '/a-test-path/'
    expected_suffix = config.Config.COMPUTED_PATH_OPTIONS[property_name]
    expected_value = '/a-test-path/%s/' % expected_suffix
    conf = config.Config()
    conf.url_path = url_path
    self.assertEqual(expected_value, conf._get_path_property(property_name))

  def test_get_path_automatic(self):
    self.check_property('automatic')

  def test_get_path_importcheck(self):
    self.check_property('importcheck')

  def test_get_path_rest(self):
    self.check_property('rest')


class ParseOptionTest(unittest.TestCase):
  """Tests for _parse_option()."""

  def test_test_package_name(self):
    self.assertEqual([], config._parse_option('test_package_names', ''))
    self.assertEqual(['a'], config._parse_option('test_package_names',
                                                     'a'))
    self.assertEqual(['a'], config._parse_option('test_package_names',
                                                     'a,'))
    self.assertEqual(['a', 'b'], config._parse_option('test_package_names',
                                                     'a, b'))
    self.assertEqual(['a', 'b'], config._parse_option('test_package_names',
                                                     'a,b'))
    self.assertEqual(['a', 'b'], config._parse_option('test_package_names',
                                                     'a,b,'))

  def test_others(self):
    self.assertEqual('a,b,', config._parse_option('foo', 'a,b,'))

class LoadConfigTest(unittest.TestCase):
  """Tests for _load_config()."""

  def setUp(self):
    self.orig_path_exists = config.os.path.exists
    self.orig_load_yaml = config._load_yaml
    self.orig_get_user_config_path = config._get_user_config_path
    # By default, checked files do exist.
    config.os.path.exists = lambda _: True
    self.default_config = {'test_package_names': 'tests',
                           'test_module_pattern': '^[\w]+_test$',
                           'url_path': '/tests/'}
    # Flag used to track if the mock _load_yaml function has been called.
    self._mock_load_yaml_called = False

  def tearDown(self):
    config.os.path.exists = self.orig_path_exists
    config._load_yaml = self.orig_load_yaml
    config._get_user_config_path = self.orig_get_user_config_path

  def get_mock_load_yaml(self, first_return, second_return):

    def mock_load_yaml(_):
      if not self._mock_load_yaml_called:
        self._mock_load_yaml_called = True
        return first_return
      else:
        return second_return

    return mock_load_yaml

  def test_missing_default(self):
    config.os.path.exists = lambda _: False
    self.assertRaises(config.ConfigError, config._load_config)

  def test_default_config_missing_option(self):
    config._get_user_config_path = lambda: None
    del self.default_config['url_path']
    config._load_yaml = self.get_mock_load_yaml(self.default_config, {})
    self.assertRaises(config.ConfigError, config._load_config)

  def test_default_config_loaded(self):
    config._get_user_config_path = lambda: None
    config._load_yaml = self.get_mock_load_yaml(self.default_config, {})
    conf = config._load_config()
    expected_values = dict(self.default_config)
    expected_values['test_package_names'] = ['tests']
    for key, value in expected_values.items():
      self.assertEqual(value, getattr(conf, key))

  def test_user_config_override(self):
    user_config = {'test_package_names': 'user_tests',
                   'test_module_pattern': 'user_^[\w]+_test$',
                   'url_path': 'user_/tests/'}
    config._get_user_config_path = lambda: None
    config._load_yaml = self.get_mock_load_yaml(self.default_config,
                                                user_config)
    config._get_user_config_path = lambda: '/mock/path'
    conf = config._load_config()
    expected_values = dict(user_config)
    expected_values['test_package_names'] = ['user_tests']
    for key, value in expected_values.items():
      self.assertEqual(value, getattr(conf, key))
