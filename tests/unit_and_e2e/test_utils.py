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

"""Tests for the utils module of aeta."""

import base64
import os
import re
import unittest

from aeta import utils
# Avoid name conflict with 2 modules named utils.
from tests import utils as tests_utils


class CheckTypeTest(unittest.TestCase):
  """Tests for the check_type function."""

  def test_same_type(self):
    utils.check_type(self, 'self', CheckTypeTest)

  def test_different_type(self):
    self.assertRaises(TypeError, utils.check_type, 1, 'one', str)

  def test_sub_type(self):
    utils.check_type(self, 'self', object)

  def test_in_tuple(self):
    utils.check_type('string!', 's', (int, str))

  def test_not_in_tuple(self):
    self.assertRaises(TypeError, utils.check_type, 'what', 's', (int, bool))


class RandUniqueIdTest(unittest.TestCase, tests_utils.MockAttributeMixin):
  """Tests for the rand_unique_id function."""

  def tearDown(self):
    self.tear_down_attributes()

  def get_ids(self):
    return [utils.rand_unique_id() for _ in range(1000)]

  def test_unique(self):
    ids = self.get_ids()
    self.assertEqual(len(ids), len(set(ids)))

  def test_url_safe(self):
    for idstr in self.get_ids():
      self.assertNotEqual(None, re.match('[a-zA-Z0-9_-]*', idstr))

  def test_invertible(self):
    """Tests invertibility with os.urandom().

    That is, the return value of os.urandom() should be inferrable from the
    return value of rand_unique_id().

    This is a fairly strong guarantee that no information is lost from
    os.urandom() to the return value of rand_unique_id(), so rand_unique_id()
    is just as random as os.urandom().
    """
    self.rand_bytes = None  # Stored return value of os.urandom().
    old_urandom = os.urandom

    @self.mock(os)
    def urandom(nbytes):
      self.assertTrue(nbytes >= 16)
      self.rand_bytes = old_urandom(nbytes)
      return self.rand_bytes

    for _ in range(1000):
      self.rand_bytes = None
      idstr = utils.rand_unique_id()
      self.assertNotEqual(None, self.rand_bytes)
      self.assertEqual(self.rand_bytes, base64.urlsafe_b64decode(idstr))


