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

"""This module contains two test functions, one that passes and one that fails.

The module is used for testing aeta functionality. Changes to this
module will result in failing tests, because exactly 1 passing and 1 failing
test function is expected.
"""




def test_pass():
  assert True


def test_fail():
  assert False, 'This test is expected to fail.'
