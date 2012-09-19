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

"""Various utilities."""

__author__ = 'jacobltaylor@gmail.com (Jacob Taylor)'

import base64
import os


def type_name(typ):
  """Returns a string representation of a type.

  Args:
    typ: The type to get a representation of.  May be an instance of type or
        a tuple of types.

  Returns:
    A string representation of typ.

  Raises:
    TypeError: Wrong input arguments.
  """
  if typ == str:
    return 'string'
  elif isinstance(typ, type):
    return typ.__name__
  elif isinstance(typ, tuple):
    return ' or '.join(type_name(t) for t in typ)
  raise TypeError('"typ" must be a type or tuple, not a %s.' % type(typ))


def check_type(obj, name, typ):
  """Check the type of an object and raise an error if it does not match.

  Args:
    obj: The object to check.
    name: Name of the object shown in a possible error message.
    typ: The expected type of obj.

  Raises:
    TypeError: if obj does not match type_.
  """
  if not isinstance(obj, typ):
    raise TypeError('"%s" (%r) must be a %s, not a %s.' %
                    (name, obj, type_name(typ), type_name(type(obj))))


def rand_unique_id():
  """Creates a random unique id made of characters safe for urls.

  Returns:
    A random id as a string.
  """
  # For maximum base64 encoding efficiency, the number of bytes should be a
  # multiple of 3.  18 bytes should be enough for anyone.
  return base64.urlsafe_b64encode(os.urandom(18))


