// Copyright 2012 Google Inc. All Rights Reserved.

// Licensed under the Apache License, Version 2.0 (the "License");
// you may not use this file except in compliance with the License.
// You may obtain a copy of the License at

//     http://www.apache.org/licenses/LICENSE-2.0

// Unless required by applicable law or agreed to in writing, software
// distributed under the License is distributed on an "AS IS" BASIS,
// WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
// See the License for the specific language governing permissions and
// limitations under the License.


// Controls the test index page.

// The page must set the following variables:

// ROOT_NAME: The full name of the test object to display, or '' if all tests
//     should be displayed.
// REST_PATH: The path to the REST interface, by default /tests/rest.


/** The namespace for aeta-related things. */
var aeta = {};


// Constants


/**
 * Should we run all tests in the root when the page loads?
 * @const
 */
aeta.RUN_ON_INIT = Boolean(location.search.match(/[?&]run/));

/**
 * The path to get method names, relative to REST_PATH.
 * @const
 */
aeta.REST_GET_METHODS_PATH = 'get_methods';

/**
 * The path to start a batch running, relative to REST_PATH.
 * @const
 */
aeta.REST_START_BATCH_PATH = 'start_batch';

/**
 * The path to retrieve general batch information, relative to REST_PATH.
 * @const
 */
aeta.REST_BATCH_INFO_PATH = 'batch_info';

/**
 * The path to poll for test results, relative to REST_PATH.
 * @const
 */
aeta.REST_BATCH_RESULTS_PATH = 'batch_results';

/**
 * How long to wait between polls to the server, in milliseconds.  The wait
 * time is incremented by this time before each call.
 * @const
 */
aeta.POLL_BATCH_WAIT_MS_INC = 500;

// Possible states a test object could be in.

/**
 * Indicates that a test has not yet been started.
 * @const
 */
aeta.STATE_UNSTARTED = 'unstarted';

/**
 * Indicates that a test is currently running.
 * @const
 */
aeta.STATE_RUNNING = 'running';

/**
 * Indicates that an error occurred when running the test.
 * @const
 */
aeta.STATE_ERROR = 'error';

/**
 * Indicates that a test failed.
 * @const
 */
aeta.STATE_FAIL = 'fail';

/**
 * Indicates that a test passed.
 * @const
 */
aeta.STATE_PASS = 'pass';

/**
 * A mapping from test state to a human-readable description.
 * @const
 */
aeta.STATE_DESCRIPTION = {
  'unstarted': 'Not started',
  'error': 'Error',
  'fail': 'Failed',
  'running': 'Running...',
  'pass': 'Passed'
};

/**
 * All test states in order.
 * Order affects how a parent test object's state depends on the states of its
 * children.  A parent's state's index in the order will be the minimum of the
 * indices of its children's states.  So for example, if the children's states
 * are aeta.STATE_FAIL and aeta.STATE_PASS, the parent's state will be
 * aeta.STATE_FAIL.
 * @const
 */
aeta.STATES_IN_ORDER = [
  aeta.STATE_UNSTARTED, aeta.STATE_RUNNING,
  aeta.STATE_ERROR, aeta.STATE_FAIL, aeta.STATE_PASS
];

/**
 * What to label the root if it contains all tests in the application.
 * @const
 */
aeta.ALL_TESTS = 'All tests';


// Utilities


/**
 * Logs a warning message to the console if possible.
 * @param {string} message The message to display.
 */
aeta.logWarning = function(message) {
  if (window.console) {
    console.log(message);
  }
};

/**
 * Makes a request to the REST server for JSON with callbacks.
 * @param {string} urlSuffix The path, relative to REST_PATH, to make a
 *     request to.
 * @param {?string} postData The payload of a POST request.  If null, this
 *     request will be a GET.
 * @param {function(*)} successCallback The function to call, with the JSON
 *     object returned by the server, on success.
 * @param {function(string)} errorCallback The function to call, with the error
 *     string returned by the server, on failure.
 */
aeta.getRestJsonData = function(urlSuffix, postData, successCallback,
                                errorCallback) {
  var type = 'POST';
  if (postData == null) {
    type = 'GET';
    postData = '';
  }
  $.ajax(REST_PATH + urlSuffix, {
    data: postData,
    dataType: 'json',
    type: type,
    success: function(data, status, xhr) {
      successCallback(data);
    },
    error: function(xhr, status, errorThrown) {
      if (errorThrown) {
        errorCallback(errorThrown + ': ' + xhr.responseText + '\n');
      } else {
        errorCallback('There was an error communicating with the server.  ' +
                      'Is the server running?\n');
      }
    }
  });
};

/**
 * Gets a list of test method names contained in the test.
 * @param {string} fullname The name of the test to query.
 * @param {function({method_names: !Array.<string>,
 *                   load_errors: !Array.<!Array.<string>>})} successCallback
 *     The function to call with the returned data, if successful.
 * @param {function(string)} errorCallback The function to call with the error
 *     message, if there is an error.
 */
aeta.getMethods = function(fullname, successCallback, errorCallback) {
  aeta.getRestJsonData(aeta.REST_GET_METHODS_PATH + '/' + fullname, null,
                       successCallback, errorCallback);
};

/**
 * Asynchronously starts a test batch running.
 * @param {string} fullname The name of the test to run.
 * @param {function(number)} successCallback The function to call with the
 *     batch id of the new batch, if successful.
 * @param {function(string)} errorCallback The function to call with the error
 *     message, if there is an error.
 */
aeta.startBatch = function(fullname, successCallback, errorCallback) {
  aeta.getRestJsonData(aeta.REST_START_BATCH_PATH + '/' + fullname, '',
                       successCallback, errorCallback);
};

/**
 * Requests general information about a test batch.
 * @param {number} batchId The id of the batch to get information for.
 * @param {function({num_units: ?number,
                     test_unit_methods: Object.<string, string>,
                     load_errors: Array.<!Array.<string>>})} successCallback
       The function to call with the information about the test, if successful.
 * @param {function(string)} errorCallback The function to call with the error
 *     message, if there is an error.
 */
aeta.batchInfo = function(batchId, successCallback, errorCallback) {
  aeta.getRestJsonData(aeta.REST_BATCH_INFO_PATH + '/' + batchId, null,
                       successCallback, errorCallback);
};

/**
 * Requests test results for a test batch.
 * @param {number} batchId The id of the batch to get information for.
 * @param {number} start The lowest index of the test unit to return results
 *     for.
 * @param {function(!Array.<{fullname: string,
 *                           load_errors: Array.<!Array.<string>>,
 *                           errors: Array.<!Array.<string>>,
 *                           failures: Array.<!Array.<string>>,
 *                           output: string}>)} successCallback The function to
 *     call with the information about the test, if successful.
 * @param {function(string)} errorCallback The function to call with the error
 *     message, if there is an error.
 */
aeta.batchResults = function(batchId, start, successCallback, errorCallback) {
  var url = aeta.REST_BATCH_RESULTS_PATH + '/' + batchId + '?start=' + start;
  aeta.getRestJsonData(url, null, successCallback, errorCallback);
};


/**
 * Returns the length of the greatest common prefix between two arrays.
 * For example, aeta.lengthCommonPrefix(['a', 'b', 'c'], ['a', 'b', 'd']) == 2.
 * @param {Array} a The first array to compare.
 * @param {Array} b The second array to compare.
 * @return {number} The length of the greatest common prefix between the
 *     arrays.
 */
aeta.lengthCommonPrefix = function(a, b) {
  for (var i = 0; i < a.length && i < b.length; ++i) {
    if (a[i] != b[i]) return i;
  }
  return i;
};


// Display functions


/**
 * The currently displayed aeta.TestObject, or null if none is displayed.
 * @type {aeta.TestObject}
 */
aeta.selectedTest = null;

/**
 * Gets the CSS class that should be applied to tests in the given state.
 * @param {string} state The test state to get a class for.
 * @return {string} The CSS class representing the state.
 */
aeta.getStateCssClass = function(state) {
  return 'aet-' + state;
};

/**
 * Creates and returns a jQuery element for the given test object.
 * @param {!aeta.TestObject} test The test object to create an element for.
 * @return {!jQuery} The jQuery element created to represent the test.
 */
aeta.createTestElement = function(test) {
  var cls = aeta.getStateCssClass(test.state);
  var element = $('<div class="aet-test ' + cls + '"></div>');
  var text = aeta.ALL_TESTS;
  if (test.fullname) {
    if (test.fullname == ROOT_NAME) {
      text = ROOT_NAME;
    } else {
      var names = test.fullname.split('.');
      text = names[names.length - 1];
    }
  }
  var label = $('<label class="aet-label"></label>').text(text);
  label.click(function() { aeta.selectTest(test); });
  element.append(label);
  return element;
};

/**
 * Sets a test to be displayed and runs it if has not been run yet.
 * This is called when a user clicks on a test.
 * @param {!aeta.TestObject} test The test object to display and maybe run.
 */
aeta.selectTest = function(test) {
  if (aeta.selectedTest) {
    aeta.selectedTest.element.removeClass('aet-selected');
  }
  aeta.selectedTest = test;
  aeta.selectedTest.element.addClass('aet-selected');
  $('#displayed-test-name').text(aeta.selectedTest.fullname || aeta.ALL_TESTS);
  aeta.updateDisplayedOutput();
  aeta.updateDisplayedState(aeta.selectedTest);
  if (test.state == aeta.STATE_UNSTARTED) {
    test.run();
  }
};

/**
 * Sets the root test element.  Should be called with the element of the root
 * test object.
 * @param {!jQuery} element The element of the root test object, which should
 *     have been returned by aeta.createTestElement().
 */
aeta.setRootTestElement = function(element) {
  $('#root').empty().append(element);
};

/**
 * Shows a test element as part of its parent's list of children on the page.
 * @param {!jQuery} parentElement The jQuery element of the parent, returned by
 *     aeta.createTestElement().
 * @param {!jQuery} childElement The jQuery element of the child, returned by
 *     aeta.createTestElement().
 * @param {number} position What the child's index in the list should be after
 *     insertion.
 */
aeta.addChildTestElement = function(parentElement, childElement, position) {
  var childList = parentElement.children('ul');
  if (!childList.length) {
    childList = $('<ul class="aet-children"></ul>').appendTo(parentElement);
  }
  var itemToAdd = $('<li class="aet-child"></li>').append(childElement);
  var childItems = childList.children('li');
  if (position == childItems.length) {
    childList.append(itemToAdd);
  } else {
    $(childItems[position]).before(itemToAdd);
  }
};

/**
 * Shows or hides the test depending on its isVisible property.
 * The test object should be displayed iff its isVisible property is true.
 * @param {!aeta.TestObject} test The test object to update visibility for.
 */
aeta.updateTestVisibility = function(test) {
  test.element.css('display', test.isVisible ? 'block' : 'none');
};

/**
 * Displays the test correctly depending on its current state.  This should be
 * called automatically whenever a test's state changes.
 * @param {!aeta.TestObject} test Update this test's displayed state.
 */
aeta.updateDisplayedState = function(test) {
  function updateElement(elem) {
    for (var i = 0; i < aeta.STATES_IN_ORDER.length; ++i) {
      elem.removeClass(aeta.getStateCssClass(aeta.STATES_IN_ORDER[i]));
    }
    elem.addClass(aeta.getStateCssClass(test.state));
  }
  updateElement(test.element);
  if (test === aeta.selectedTest) {
    updateElement($('#displayed-test-name'));
    // If not already running, show the "Run again" button.
    var showRunAgain = aeta.selectedTest.state != aeta.STATE_RUNNING;
    $('#run-again').css('display', showRunAgain ? 'block' : 'none');
  }
};

/** Displays the selected test's output in the output box. */
aeta.updateDisplayedOutput = function() {
  if (aeta.selectedTest) {
    $('#output').text(aeta.selectedTest.getOutput());
  }
};


// Test logic


/**
 * Represents a test object (root, package, module, class, or method).
 * @constructor
 * @param {!aeta.TestIndex} aeta.testIndex The index containing this test.
 * @param {string} fullname The full name (with dots) of the test object.
 * @param {!aeta.TestObject} parent The test object containing this one, or
 *     null if this is the root.
 */
aeta.TestObject = function(testIndex, fullname, parent) {
  /**
   * The index containing this test object.
   * @type {!aeta.TestIndex}
   */
  this.testIndex = testIndex;

  /**
   * The full name of this test object.
   * @type {string}
   */
  this.fullname = fullname;

  /**
   * The parent aeta.TestObject, or null if this is the root.  For example if
   * this is a method then the parent will be the containing class.
   * @type {!aeta.TestObject}
   */
  this.parent = parent;

  /**
   * An array of aeta.TestObjects whose parent is this.
   * Sorted by fullname.
   * @type {!Array.<!aeta.TestObject>}
   */
  this.children = [];

  /**
   * The current state of the test (a aeta.STATE_* constant).
   * @type {string}
   */
  this.state = aeta.STATE_UNSTARTED;

  /**
   * List of messages applied to this aeta.TestObject.  This test's getOutput()
   * will contain these messages in addition to all messages of children and
   * ancestors.
   * @type {!Array.<string>}
   */
  this.messages = [];

  /**
   * The jQuery element representing this test in the index.
   * @type {!jQuery}
   */
  this.element = aeta.createTestElement(this);

  /**
   * Whether or not the test object should be visible to the user.
   * @type {boolean}
   */
  this.isVisible = true;

  if (parent) {
    parent.addChild(this);
  } else {
    aeta.setRootTestElement(this.element);
  }
};

/**
 * Adds a child to the test object.
 * This should only be called once, in the constructor for the child.
 * @param {!aeta.TestObject} newChild The child test object.
 */
aeta.TestObject.prototype.addChild = function(newChild) {
  // Keep the children sorted by name.
  // Go backwards because the children are likely to be added in order due to
  // the way the server produces output.
  for (var i = this.children.length - 1; i >= 0; --i) {
    if (newChild.fullname >= this.children[i].fullname) break;
  }
  var position = i + 1;
  this.children.splice(position, 0, newChild);
  aeta.addChildTestElement(this.element, newChild.element, position);
};

/**
 * Adds a message to the test object.
 * This message will become part of the getOutput() of this object, its
 * parents, and its children.
 * @param {string} msg The message to add.
 */
aeta.TestObject.prototype.addMessage = function(msg) {
  this.messages.push(msg);
};

/**
 * Recursively applies functions to this test object and all direct and
 * indirect children.  This can either do preorder or postorder traversal.
 *
 * @param {function(!aeta.TestObject)} fn A function applied to each object.
 * @param {?boolean} isPostorder Whether to do a postorder traversal.  By
 *     default the traversal is preorder.
 */
aeta.TestObject.prototype.forEachContained = function(fn, isPostorder) {
  if (!isPostorder) fn(this);
  for (var i = 0; i < this.children.length; ++i) {
    this.children[i].forEachContained(fn, isPostorder);
  }
  if (isPostorder) fn(this);
};

/**
 * Gets the output message for this object.
 * The message is formed from the messages of this object, its children, and
 * its ancestors.  It is displayed to the user when this test is selected.
 * @return {string} The output message.
 */
aeta.TestObject.prototype.getOutput = function() {
  var lines = [aeta.STATE_DESCRIPTION[this.state], ''];
  function addMessages(test) {
    for (var i = 0; i < test.messages.length; ++i) {
      lines.push('In ' + (test.fullname || aeta.ALL_TESTS) + ':');
      lines.push(test.messages[i]);
    }
  }
  this.forEachContained(addMessages);
  for (var par = this.parent; par != null; par = par.parent) {
    addMessages(par);
  }
  return lines.join('\n');
};

/**
 * Recomputes this object's state as a function of its children's states.
 * Its children's states should already be correct.  This should only be called
 * on container objects, not individual methods.  The computed state follows
 * the rules of aeta.STATES_IN_ORDER, so for example a test with any of its
 * children aeta.STATE_UNSTARTED will also be aeta.STATE_UNSTARTED.
 */
aeta.TestObject.prototype.recomputeState = function() {
  var someChildHasState = {};
  for (var i = 0; i < this.children.length; ++i) {
    someChildHasState[this.children[i].state] = true;
  }
  var newState = aeta.STATE_PASS;
  for (var i = 0; i < aeta.STATES_IN_ORDER.length; ++i) {
    var state = aeta.STATES_IN_ORDER[i];
    if (someChildHasState[state]) {
      newState = state;
      break;
    }
  }
  if (newState != this.state) {
    this.state = newState;
    aeta.updateDisplayedState(this);
    if (this.parent) {
      this.parent.recomputeState();
    }
  }
};

/**
 * Sets this object's state in addition to the states of all its direct and
 * indirect children.
 * @param {string} newState What the object and its children's state should be.
 */
aeta.TestObject.prototype.setState = function(newState) {
  this.forEachContained(function(test) {
    test.state = newState;
    aeta.updateDisplayedState(test);
    test.recomputeVisibility();
  }, true);
  if (this.parent) {
    this.parent.recomputeState();
    this.parent.recomputeVisibility(true);
  }
};

/**
 * Removes all messages in this object and its direct and indirect children.
 */
aeta.TestObject.prototype.recursivelyClearMessages = function() {
  this.forEachContained(function(test) { test.messages = []; });
};

/**
 * Asynchronously starts running this test.
 * This will eventually update the test with results from the server.
 */
aeta.TestObject.prototype.run = function() {
  this.recursivelyClearMessages();
  this.setState(aeta.STATE_RUNNING);
  aeta.updateDisplayedOutput();
  new aeta.TestResultUpdater(this.testIndex, this.fullname).startBatch();
};

/**
 * Sets the object's isVisible property to the correct value and shows/hides it
 * accordingly.
 * The object should be visible iff it or any of its descendents has a state
 * that should be visible.
 * @param {boolean} updateParent Whether to update all ancestors' visibilites
 *     as well.
 */
aeta.TestObject.prototype.recomputeVisibility = function(updateParent) {
  var visible = this.testIndex.visibleStates.indexOf(this.state) != -1;
  for (var i = 0; !visible && i < this.children.length; ++i) {
    if (this.children[i].isVisible) {
      visible = true;
    }
  }
  if (visible != this.isVisible) {
    this.isVisible = visible;
    aeta.updateTestVisibility(this);
    if (updateParent && this.parent) {
      this.parent.recomputeVisibility(true);
    }
  }
};

/**
 * Updates the visibility of this object, all its direct or indirect children,
 * and its ancestors.
 */
aeta.TestObject.prototype.updateVisibility = function() {
  // Update visibility of children before parents.
  this.forEachContained(function(test) { test.recomputeVisibility(); }, true);
  if (this.parent) {
    this.parent.recomputeVisibility(true);
  }
};

/**
 * An index keeping track of all test objects on the page.
 * @constructor
 */
aeta.TestIndex = function() {
  /**
   * A mapping from object fullname to test object.
   * @type {!Object.<string, !aeta.TestObject>}
   */
  this.testObjects = {};

  /**
   * An array of states that should be visible.
   * @type {!Array<string>}
   */
  this.visibleStates = aeta.STATES_IN_ORDER;

  /**
   * The root aeta.TestObject (with name ROOT_NAME).
   * @type {!aeta.TestObject}
   */
  this.root = new aeta.TestObject(this, ROOT_NAME, null);
  this.testObjects[ROOT_NAME] = this.root;
};

/**
 * Gets the named test object if it exists, otherwise adds and returns it.
 * @param {string} fullname The full name of the test object.
 * @return {!aeta.TestObject} The existing or created test object.
 */
aeta.TestIndex.prototype.getOrAdd = function(fullname) {
  var alreadyPresent = this.testObjects[fullname];
  if (alreadyPresent) return alreadyPresent;
  var names = fullname ? fullname.split('.') : [];
  var rootNames = ROOT_NAME ? ROOT_NAME.split('.') : [];

  // Create all prefixes of the test starting from the root.  For example if
  // the root is a package and this test is a method in the module, then the
  // module, class, and method of the test must be created.
  var start = aeta.lengthCommonPrefix(names, rootNames);
  var parent = this.root;
  for (var i = start; i < names.length; ++i) {
    var prefix = names.slice(0, i + 1).join('.');
    var test = this.testObjects[prefix];
    if (!test) {
      test = this.testObjects[prefix] =
          new aeta.TestObject(this, prefix, parent);
    }
    parent = test;
  }
  return parent;
};

/**
 * Convenience function to add an error message to the given test object.
 * @param {string} fullname The name of the test object.
 * @param {string} message The error message.
 * @param {?string} state The new state of the test object, by default
 *     aeta.STATE_ERROR.
 */
aeta.TestIndex.prototype.addError = function(fullname, message, state) {
  var test = this.getOrAdd(fullname);
  test.setState(state || aeta.STATE_ERROR);
  test.addMessage(message);
};

/**
 * Convenience function to add multiple error messages.
 * Same as calling addError() for every individual error.
 * @param {!Array.<!Array.<string>>} errs An array of [fullname, error message]
 *     for errors to add.
 * @param {?string} state The new state of the test objects, by defualt
 *     aeta.STATE_ERROR.
 */
aeta.TestIndex.prototype.addErrors = function(errs, state) {
  for (var i = 0; i < errs.length; ++i) {
    this.addError(errs[i][0], errs[i][1], state);
  }
};


/**
 * Handles an interaction with the server to run a specific test object.
 * @constructor
 * @param {!aeta.TestIndex} aeta.testIndex The aeta.TestIndex that should be
 *     updated with results.
 * @param {string} fullname The full name of the test object to run.
 */
aeta.TestResultUpdater = function(testIndex, fullname) {
  /**
   * The full name of the test object to run.
   * @type string
   */
  this.fullname = fullname;

  /**
   * Whether or not this test has already started.
   * @type boolean
   */
  this.hasStarted = false;

  /**
   * How long, in milliseconds, to sleep the next time before polling the
   * server.  This will be incremented by aeta.POLL_BATCH_WAIT_MS_INC each
   * poll.
   * @type number
   */
  this.sleepTime = 0;

  /**
   * The aeta.TestIndex that should be updated with results.
   * @type {!aeta.TestIndex}
   */
  this.testIndex = testIndex;

  /**
   * The numeric id of this test's batch, or null if this is not known.
   * @type {?number}
   */
  this.batchId = null;

  /**
   * The number of test units contained in this object, or null if this number
   * is not known.
   * @type {?number}
   */
  this.numUnits = null;

  /**
   * The number of test units that have already been processed.
   * @type {number}
   */
  this.numUnitsFinished = 0;

  /**
   * A mapping from test unit name to a list of test method fullnames contained
   * in that unit, or null if this mapping is not yet known.
   * @type {Object.<string, !Array.<string>>}
   */
  this.testUnitMethods = null;
};

/**
 * Gets an error callback function.
 * The callback function will notify the test index that an error occurred.
 * @return {function(string)} A callback function appropriate for
 *     aeta.getRestJsonData.
 */
aeta.TestResultUpdater.prototype.getErrorCallback = function() {
  var self = this;  // So closures work.
  return function(message) {
    self.testIndex.addError(self.fullname, message);
    aeta.updateDisplayedOutput();
  };
};

/**
 * Processes and updates batch info when it is available.
 * @param {*} info The batch info JSON to update.
 */
aeta.TestResultUpdater.prototype.updateBatchInfo = function(info) {
  this.numUnits = info.num_units;
  this.testUnitMethods = info.test_unit_methods;
  for (var testUnit in this.testUnitMethods) {
    var methods = this.testUnitMethods[testUnit];
    for (var i = 0; i < methods.length; ++i) {
      this.testIndex.getOrAdd(methods[i]).setState(aeta.STATE_RUNNING);
    }
  }
  this.testIndex.addErrors(info.load_errors);
  aeta.updateDisplayedOutput();
};

/**
 * Processes and updates test results when they are available.
 * @param {!Array.<*>} results A list of result JSON objects.
 */
aeta.TestResultUpdater.prototype.updateResults = function(results) {
  for (var i = 0; i < results.length; ++i) {
    var result = results[i];
    this.testIndex.addErrors(result.load_errors);
    this.testIndex.addErrors(result.errors);
    this.testIndex.addErrors(result.failures, aeta.STATE_FAIL);
    // All methods in the unit that haven't failed/errored must have passed.
    var methodNames = this.testUnitMethods[result.fullname];
    for (var j = 0; j < methodNames.length; ++j) {
      var test = this.testIndex.getOrAdd(methodNames[j]);
      if (test.state != aeta.STATE_ERROR && test.state != aeta.STATE_FAIL) {
        if (test.state != aeta.STATE_RUNNING) {
          aeta.logWarning('Test ' + test.fullname + ' was expected to be ' +
                          ' running but was ' + test.state + '.');
        }
        test.setState(aeta.STATE_PASS);
      }
    }
    if (result.output) {
      this.testIndex.getOrAdd(result.fullname).addMessage(result.output);
    }
  }
  aeta.updateDisplayedOutput();
  this.numUnitsFinished += results.length;
};

/** Starts running the test object. */
aeta.TestResultUpdater.prototype.startBatch = function() {
  if (!this.hasStarted) {
    this.hasStarted = true;
    var self = this;
    aeta.startBatch(this.fullname, function(data) {
      if (data.batch_id) {
        self.batchId = data.batch_id;
        self.initializeBatchInfo();
      } else {
        self.updateBatchInfo(data.batch_info);
        self.updateResults(data.results);
      }
    }, this.getErrorCallback());
  }
};

/**
 * Initializes general information about the test batch by polling the server.
 * Should only be called internally in startBatch().
 */
aeta.TestResultUpdater.prototype.initializeBatchInfo = function() {
  var self = this;
  if (this.batchId == null) {
    aeta.logWarning('Called TestResultUpdater.initializeBatchInfo() before ' +
                    'startBatch()');
    return;
  }
  aeta.batchInfo(this.batchId, function(info) {
    if (!info) {
      self.sleepTime += aeta.POLL_BATCH_WAIT_MS_INC;
      setTimeout(function() { self.initializeBatchInfo(); }, self.sleepTime);
    } else {
      self.updateBatchInfo(info);
      self.sleepTime = 0;
      self.pollResults();
    }
  }, this.getErrorCallback());
};

/**
 * Continues polling the server for test results until all have been processed.
 * Notifies the test index of any test results.
 * Should only be called internally in initializeBatchInfo().
 */
aeta.TestResultUpdater.prototype.pollResults = function() {
  var self = this;
  if (this.testUnitMethods == null) {
    aeta.logWarning('Called TestResultUpdater.pollResults() before ' +
                    'initializeBatchInfo()');
    return;
  }
  aeta.batchResults(this.batchId, this.numUnitsFinished, function(results) {
    self.updateResults(results);
    if (self.numUnitsFinished < self.numUnits) {
      if (results.length) self.sleepTime = 0;
      self.sleepTime += aeta.POLL_BATCH_WAIT_MS_INC;
      setTimeout(function() { self.pollResults(); }, self.sleepTime);
    }
  }, this.getErrorCallback());
};


// Controls and initialization

/**
 * The aeta.TestIndex of the page.
 * @type {!aeta.TestIndex}
 */
aeta.testIndex = null;

/** Initializes the index with tests received from the server. */
aeta.initializeTests = function() {
  aeta.getMethods(ROOT_NAME, function(data) {
    for (var i = 0; i < data.method_names.length; ++i) {
      aeta.testIndex.getOrAdd(data.method_names[i]);
    }
    aeta.testIndex.addErrors(data.load_errors);
    $('#loading').css('display', 'none');
  }, function(err) {
    aeta.testIndex.addError(ROOT_NAME, err);
  });
};

/** Adds click handlers for resizing panels. */
aeta.initializePanels = function() {
  function expandCollapse(expand, collapse) {
    collapse.removeClass('larger-panel').addClass('smaller-panel');
    expand.removeClass('smaller-panel').addClass('larger-panel');
  }
  $('#root').click(function() {
    expandCollapse($('#left'), $('#right'));
  });
  $('#output').click(function() {
    expandCollapse($('#right'), $('#left'));
  });
};

/** Adds a click handler for the "Run again" button. */
aeta.initializeRunAgain = function() {
  $('#run-again').click(function() {
    if (aeta.selectedTest) {
      aeta.selectedTest.run();
    }
  });
};

/** Updates the visible states based on the states of the check boxes. */
aeta.updateVisibleStates = function() {
  aeta.testIndex.visibleStates = $.grep(aeta.STATES_IN_ORDER, function(state) {
    return $('#show-' + state).is(':checked');
  });
  aeta.testIndex.root.updateVisibility();
};

/** Adds click handlers for the visibility check boxes. */
aeta.initializeVisibilityCheckboxes = function() {
  for (var i = 0; i < aeta.STATES_IN_ORDER.length; ++i) {
    $('#show-' + aeta.STATES_IN_ORDER[i]).click(aeta.updateVisibleStates);
  }
};

/**
 * Initializes the page.
 * This should only be called when the page is ready.
 */
aeta.initialize = function() {
  aeta.testIndex = new aeta.TestIndex();
  aeta.initializeTests();
  aeta.initializePanels();
  aeta.initializeRunAgain();
  aeta.initializeVisibilityCheckboxes();
  if (aeta.RUN_ON_INIT) {
    aeta.selectTest(aeta.testIndex.root);
  }
};
