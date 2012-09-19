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

"""File access tests for App Engine."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

import inspect
import unittest


class FileAccessTest(unittest.TestCase):
  """Tests for file access on App Engine."""

  def setUp(self):
    self.module = inspect.getmodule(self)
    self.file = inspect.getsourcefile(self.module)

  def test_open_permissions(self):
    metamodes = ['', 'b', 'U']
    # no mode given
    tmp = open(self.file)
    tmp.close()
    # allowed modes
    allowed_modes = ['r']
    for mode in allowed_modes:
      for metamode in metamodes:
        tmp = open(self.file, mode + metamode)
        tmp.close()
    # disallowed modes
    disallowed_modes = ['r+', 'w', 'w+', 'a', 'a+']
    for mode in disallowed_modes:
      for metamode in metamodes:
        self.assertRaises(IOError, open, self.file, mode + metamode)

  def test_read_correctness(self):
    module_source = inspect.getsource(self.module).splitlines()
    tmp = open(self.file)
    file_source = tmp.read().splitlines()
    tmp.close()
    self.assertEqual(len(module_source), len(file_source))
    for i in range(len(module_source)):
      self.assertEqual(module_source[i], file_source[i])
