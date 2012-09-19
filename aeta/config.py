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

"""aeta configuration."""



import os

import yaml


__all__ = ['Config',
           'get_config',
           ]

YAML_FILE_NAME = 'aeta.yaml'

# A loaded Config object.
_LOADED_CONFIG = None


class ConfigError(Exception):
  """Raised when a config could not be created."""


# some attribute magic in this class - pylint:disable-msg=E1101
class Config(object):
  """aeta configuration object.

  The configuration has a limited set of valid options that can be set and
  additionally a number of options that can only be retrieved (as they are
  computed).

  Due to the use case of Config objects, it is assumed options are set only
  once and not modified afterwards.
  """

  # Options that can be set.  See aeta.yaml for details about the options.
  SET_OPTIONS = ['test_package_names',
                 'test_module_pattern',
                 'url_path',
                 'use_appstats',
                 'parallelize_modules',
                 'parallelize_classes',
                 'parallelize_methods',
                 'test_queue',
                 'storage',
                 'protected',
                 'permitted_emails',
                 'include_test_functions',
                 ]

  # Options which are computed based on url_path.
  COMPUTED_PATH_OPTIONS = {'rest': 'rest',
                           'deferred': 'deferred',
                           'static': 'static',
                           }

  NOT_SET = 'NOT SET'

  def __init__(self, **kwargs):
    for option in Config.SET_OPTIONS:
      setattr(self, option, Config.NOT_SET)
    for option in Config.COMPUTED_PATH_OPTIONS:
      private_name = '_' + option
      setattr(self, private_name, Config.NOT_SET)
    for name, value in kwargs.items():
      if name not in Config.SET_OPTIONS:
        raise ConfigError('"%s" is not a valid option to set.' % name)
      setattr(self, name, value)

  def _get_path_property(self, name):
    """Get value of path property with the given name."""
    suffix = Config.COMPUTED_PATH_OPTIONS[name]
    if self.url_path == Config.NOT_SET:
      raise ConfigError('"url_path" has not been set.')
    private_name = '_' + name
    if getattr(self, private_name) == Config.NOT_SET:
      value = '/'.join([self.url_path.rstrip('/'), suffix]) + '/'
      setattr(self, private_name, value)
    return getattr(self, private_name)

  @property
  def url_path_rest(self):
    """Read-only property."""
    return self._get_path_property('rest')

  @property
  def url_path_deferred(self):
    """Read-only property."""
    return self._get_path_property('deferred')

  @property
  def url_path_static(self):
    """Read-only property."""
    return self._get_path_property('static')


def _get_user_config_path():
  """Get path to user config file.

  Returns:
    the path to the user config file if it was found, None otherwise.
  """
  current_dir = os.path.dirname(__file__)
  while True:
    app_yaml_path = os.path.join(current_dir, 'app.yaml')
    if os.path.exists(app_yaml_path):
      user_yaml_path = os.path.join(current_dir, YAML_FILE_NAME)
      if os.path.exists(user_yaml_path):
        return user_yaml_path
      else:
        return None
    current_dir = os.path.dirname(current_dir)
    if current_dir == os.sep:
      return None


def _load_yaml(path):
  """Load YAML data from path.

  This is a simple wrapper to make testing easier.

  Args:
    path: The path of the YAML configuration file.

  Returns:
    A dictionary matchig the data from the provided yaml file.
  """
  return yaml.load(open(path).read())


def _parse_option(option_name, option_value):
  """Parse an option value and return the parsed value.

  Args:
    option_name: Name of the option.
    option_value: Value of the option.

  Returns:
    The parsed option value
  """
  if option_name in ['test_package_names', 'permitted_emails']:
    option_value = (option_value or '').strip(', ')
    names = [name.strip() for name in option_value.split(',')]
    return [name for name in names if name]
  else:
    return option_value


def _load_config():
  """Load configuration for aeta."""
  default_yaml_path = os.path.join(os.path.dirname(__file__), YAML_FILE_NAME)
  if not os.path.exists(default_yaml_path):
    msg = 'No default configuration file found at %s' % default_yaml_path
    raise ConfigError(msg)
  default_yaml_config = _load_yaml(default_yaml_path)
  config = Config()
  for option_name in Config.SET_OPTIONS:
    if option_name not in default_yaml_config:
      msg = ('No setting for "%s" option found in default '
             'config file' % option_name)
      raise ConfigError(msg)
    option_value = _parse_option(option_name, default_yaml_config[option_name])
    setattr(config, option_name, option_value)
  user_yaml_path = _get_user_config_path()
  if user_yaml_path:
    user_yaml_config = _load_yaml(user_yaml_path)
    for option_name in Config.SET_OPTIONS:
      if option_name not in user_yaml_config:
        continue
      option_value = _parse_option(option_name, user_yaml_config[option_name])
      setattr(config, option_name, option_value)
  return config


def get_config():
  """Get aeta configuration."""
  # Use global as we assign the value, as well - pylint:disable-msg=W0603
  global _LOADED_CONFIG
  if not _LOADED_CONFIG:
    _LOADED_CONFIG = _load_config()
  return _LOADED_CONFIG
