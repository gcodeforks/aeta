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

"""A dummy application to check the file upload limit."""

from google.appengine.ext import webapp
from google.appengine.ext.webapp import util

_quote = """Let me put it this way, Mr. Amer. The 9000 series is the most
reliable computer ever made. No 9000 computer has ever made a mistake or
distorted information. We are all, by any practical definition of the
words, foolproof and incapable of error.

<br/>
<br/>
Looking for the tests? Go here: <a href="/tests/">/tests/</a>
"""


class RequestHandler(webapp.RequestHandler):

  def get(self):
    self.response.out.write(_quote)


APP = webapp.WSGIApplication([('/.*', RequestHandler)])


def main():
  util.run_wsgi_app(APP)


if __name__ == '__main__':
  main()
