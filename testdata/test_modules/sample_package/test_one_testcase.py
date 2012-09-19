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

"""This module contains 1 test case with a passing and a failing test.

The module is used for testing aeta functionality. Changes to this
module will result in failing tests, because exactly 1 test case with
exactly 1 passing and 1 failing test is expected.
"""



import unittest


class SimpleTestCase(unittest.TestCase):

  def test_pass(self):
    self.assertTrue(True)

  def test_fail(self):
    self.assertTrue(False, 'This test is expected to fail.')
