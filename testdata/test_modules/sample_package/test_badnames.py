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

"""This module contains test objects with unexpected __name__ attributes.

It is used for testing aeta.logic.
"""



import unittest


# Change the module's __name__.  The module's __name__ no longer starts with
# 'test_'; nevertheless, it should be included in the test suite because it was
# imported as test_badnames.
__name__ = 'module_name'


class ClassWithDifferentModule(unittest.TestCase):

  def test_method(self):
    pass


ClassWithDifferentModule.__module__ = 'class_module'


class ClassWithDifferentName1(unittest.TestCase):

  def test_method(self):
    pass


class ClassWithDifferentName2(unittest.TestCase):

  def test_method(self):
    pass


# Make the classes be named the same thing.  This could happen due to e.g.
# using the same decorator that doesn't set __name__ properly.
ClassWithDifferentName1.__name__ = 'ClassName'
ClassWithDifferentName2.__name__ = 'ClassName'


class ClassWithDifferentMethodNames(unittest.TestCase):

  def test_method1(self):
    pass

  def test_method2(self):
    pass


# Make the methods be named the same thing.  This could happen due to e.g.
# using the same decorator that didn't set __name__ properly.  Notice that the
# method names do not start with 'test_'; nevertheless, they should be included
# in the test suite because the attribute names start with __test__.
ClassWithDifferentMethodNames.test_method1.im_func.__name__ = 'method_name'
ClassWithDifferentMethodNames.test_method2.im_func.__name__ = 'method_name'

