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

"""This module represents a working module without test cases.

Although it contains no unittest, aeata will need to load it in order
to find that it provides no such tests.

With the default test module name pattern, this module will not be
loaded, but it will for a pattern which would match this module's
name.

It is used for testing aeta.logic.
"""




class Foo(object):

  def bar(arg):
    return arg


def baz():
  return 42
