# App Engine Test Appendix (aeta) #
aeta is a package that helps you run tests for your Python App Engine application, either in the test (your SDK) or in the production environment.

## Instructions ##

First, download aeta and copy the aeta folder into your application directory:

```
git clone https://code.google.com/p/aeta/
cp -r aeta/aeta myapp/
```

You should have a folder called `aeta` in your application directory now.

Next, add a handler for aeta in your app.yaml file:
```
handlers:
<your handlers here...>
- url: /tests/.*
  script: aeta.main.APP
```

or if you are using Python 2.5:

```
- url: /tests/.*
  script: aeta/main.py
```

Now make a directory called `tests` and files called `__init__.py` and `first_test.py` in that directory:
```
cd myapp
mkdir tests
touch tests/__init__.py
echo '
import unittest

class FirstTest(unittest.TestCase):

	def test_hello(self):
		print "Hello!"

	def test_fail(self):
		self.assertEqual(1, 2)
' > tests/first_test.py
```

Next, either deploy your application or run it with dev\_appserver.py.

For deployed applications, go to the appropriate URL for your application followed by `/tests/`, like `example.appspot.com/tests/`.  For dev\_appserver.py, go to `localhost:8080/tests/`.  You should see a view of your tests.  Click tests to run them and see their results.

## How it Works ##

aeta will find all tests in the "tests" package.  Each module file must end in "`_test.py`".  The test classes in the module should derive from `unittest.TestCase`.  Refer to the unittest documentation (link) for more details on writing test cases.

The `tests` package can also have sub-packages.  Like any Python package, they must contain a file called `__init__.py`.

Behind the scenes, aeta runs tests in the task queue in parallel.  This will make large test suites run quickly.

## Advanced Usage ##

### Command Line Interface ###

You can also run tests from the command line.  First, start up the server as before.  Next, run the following command:
```
aeta/local_client.py http://example.appspot.com/tests/
```
replacing `example.appspot.com` with the hostname of your application, or `localhost:8080` for dev\_appserver.  For security reasons, this will prompt you to enter your Google username and password, unless you are using dev\_appserver.py.

To run a specific test, you can enter a command like this:
```
aeta/local_client.py http://example.appspot.com/tests/ tests.first_test.FirstTest.test_hello
```

The second argument can be any test object: a package like `tests`, a module like `tests.first_test`, a class like `tests.first_test.FirstTest`, or a method like `tests.first_test.FirstTest.test_hello`.

### Configuration ###

The default settings will work for most users, but advanced users might want more control over how tests are discovered and run.  To configure aeta, create a file called aeta.yaml in your application directory.  This file should look similar to aeta/aeta.yaml, the default settings file.  The following options are available:

| Option | Description | Default |
|:-------|:------------|:--------|
| test\_package\_names | The names of test packages to include in the test suite.  Separate test packages by commas. | tests |
| test\_module\_pattern | The regular expression of modules which to include in tests. | ^test`_`[\w]+$ |
| url\_path | URL path to the web interface for aeta.  This should match the pattern in app.yaml. | /tests/ |
| parallelize\_modules | Whether to run multiple modules in parallel. | true |
| parallelize\_classes | Whether to run multiple classes in parallel. | false |
| parallelize\_methods | Whether to run multiple methods in parallel (not recommended). | false |
| test\_queue | Which queue to use to run tests.  To improve performance, developers can switch this to another queue and increase its rate. | default |
| storage | What method to use to store test results.  Use "datastore" to store results in the datastore or "memcache" to store results in memcache.  The "memcache" setting may cause errors due to unreliability.  You can also use "immediate" to run tests in the request handler.  This is fast for short tests but does not allow parallelism and could time out. | datastore |
| protected | Whether aeta should require authorization to run tests.  Recommended for publicly accessible applications. | true |
| permitted\_emails | Comma-separated list of email addresses of users who can run tests. No need to add admin users. |  |
| include\_test\_functions | Whether to include test functions (functions in the module that start with "test") as part of the test module.  If they are included, they will be included in an extra class whose name is based on the module's name.  For example, if the `test_unicode` module contains a function `test_text()`, then this test can be accessed as `test_unicode.TestUnicodeWrappedTestFunctions.test_text`. | true |

