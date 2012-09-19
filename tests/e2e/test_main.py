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

"""Tests for the entry point of aeta."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

import unittest

from aeta import config
from aeta import main


# pylint: disable-msg=C0103,C0111,W0212
class GetUrlMappingTest(unittest.TestCase):
  """Tests for get_url_mapping()."""

  def setUp(self):
    self.orig_get_config = config.get_config
    self.url_path = '/test-all/'

  def tearDown(self):
    config.get_config = self.orig_get_config

  # config attributes dynamically assigned - pylint:disable-msg=E1101
  def test_mapping(self):
    conf = config.Config(url_path='/test-all/')
    config.get_config = lambda : conf
    mapping = main.get_url_mapping()
    found_importcheck_path = False
    found_automatic_path = False
    found_default_path = False
    for path, _ in mapping:
      if path == conf.url_path_importcheck + '(.*)':
        found_importcheck_path = True
      if path == conf.url_path_automatic + '(.*)':
        found_automatic_path = True
      if path == conf.url_path + '.*':
        found_default_path = True
    self.assertTrue(found_importcheck_path)
    self.assertTrue(found_automatic_path)
    self.assertTrue(found_default_path)
