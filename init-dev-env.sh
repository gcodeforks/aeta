#!/bin/bash
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

# This must be called from the repository root:
# source ./init-dev-env.sh PATH_TO_SDK

if [ `basename $0` = init-dev-env.sh ]; then
  echo "Script must be sourced rather than run normally."
  exit 1
fi


if [ $# -ne 1 ]; then
  echo "Exactly 1 argument expected: Path to the App Engine SDK."
  return 1
fi

PYTHONPATH=$(pwd)/lib/:
PYTHONPATH=$PYTHONPATH:$1
PYTHONPATH=$PYTHONPATH:$1/lib/django_0_96/
export PYTHONPATH=$PYTHONPATH:
export PYLINTRC=$(pwd)


# Create symbolic links.
for app in testdata/e2e_{25,27}_app; do
  ln -snf aeta $app/aeta
  ln -snf tests/e2e $app/e2e_tests
  ln -snf tests/unit_and_e2e $app/unit_and_e2e_tests
  mkdir -p $app/tests/
  ln -snf tests/__init__.py $app/tests/__init__.py
  ln -snf tests/test_utils.py $app/tests/test_utils.py
done
ln -snf aeta demo/aeta
