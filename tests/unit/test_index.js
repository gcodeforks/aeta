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

// Tests for index.js.


// Support for mocking properties of objects, which are automatically reset.

tearDownFunctions = [];

function setUp() {
  REST_PATH = '/tests/rest';
  ROOT_NAME = '';
  tearDownFunctions = [];

  aeta.selectedTest = null;
  $('#output').text('No test selected.');
  $('#run-again').css('display', 'none');
  $('#loading').css('display', 'inline');
  $('.aet-show-box').attr('checked', 'checked');
}

function tearDown() {
  // LIFO order works if the same property is mocked multiple times.
  while (tearDownFunctions.length) {
    tearDownFunctions.pop()();
  }
}

/**
 * Temporarily sets a property of an object.
 * It will automatically be reset to its old value when the test ends.
 * @param {!Object} obj The object to temporarily set a property of.
 * @param {string} name The name of the property.
 * @param {*} newValue The temporary value of the property.
 */
function mockProperty(obj, name, newValue) {
  var oldValue = obj[name];
  tearDownFunctions.push(function() { obj[name] = oldValue; });
  obj[name] = newValue;
}

/**
 * Asserts that the contents of 2 arrays are equal.
 * @param {!Array} a The first array.
 * @param {!Array} b The second array.
 */
function assertArrayEquals(a, b) {
  assertEquals(a.length, b.length);
  for (var i = 0; i < a.length; ++i) {
    assertEquals(a[i], b[i]);
  }
}


// Tests for utilities.


function testLengthCommonPrefix() {
  assertEquals(0, aeta.lengthCommonPrefix(['a', 'b'], ['c']));
  assertEquals(2, aeta.lengthCommonPrefix(['a', 'b', 'c'], ['a', 'b', 'd']));
  assertEquals(2, aeta.lengthCommonPrefix(['a', 'b'], ['a', 'b', 'd']));
  assertEquals(0, aeta.lengthCommonPrefix(['a', 'b'], []));
}


// Tests for display functions.

/**
 * Creates and returns a aeta.TestIndex with some objects in it.
 * @return {!aeta.TestIndex} The created TestIndex.
 */
function createTestIndex() {
  var index = new aeta.TestIndex();
  index.getOrAdd('package1.module2');
  index.getOrAdd('package1.module1');
  index.getOrAdd('package3');
  index.getOrAdd('package2');
  index.getOrAdd('package1.module1.Class1.method1');
  index.getOrAdd('package1.module1.Class2.method2');
  return index;
}

function testCreateTestElement() {
  var index = new aeta.TestIndex();
  var test = index.getOrAdd('package.module');
  assertTrue(index.root.element.is('.aet-test.aet-unstarted'));
  assertEquals(aeta.ALL_TESTS, index.root.element.children('label').text());
  assertTrue(test.element.is('.aet-test.aet-unstarted'));
  assertEquals('module', test.element.children('label').text());
}

function testCreateTestElementNamedRoot() {
  ROOT_NAME = 'package.module';
  var index = new aeta.TestIndex();
  assertTrue(index.root.element.is('.aet-test.aet-unstarted'));
  assertEquals('package.module', index.root.element.children('label').text());
}

function testSelectTest() {
  mockProperty(aeta.TestObject.prototype, 'run', function() {
    assertFalse(this.state == aeta.STATE_RUNNING);
    this.setState(aeta.STATE_RUNNING);
  });
  var index = createTestIndex();
  aeta.selectTest(index.getOrAdd('package1'));
  assertEquals(aeta.selectedTest, index.getOrAdd('package1'));
  assertTrue(aeta.selectedTest.element.hasClass('aet-selected'));
  assertEquals('package1', $('#displayed-test-name').text());
  assertEquals(aeta.STATE_RUNNING, aeta.selectedTest.state);

  aeta.selectTest(index.getOrAdd('package2'));
  assertEquals(aeta.selectedTest, index.getOrAdd('package2'));
  assertTrue(aeta.selectedTest.element.hasClass('aet-selected'));
  assertFalse(index.getOrAdd('package1').element.hasClass('aet-selected'));
  assertEquals('package2', $('#displayed-test-name').text());
  assertEquals(aeta.STATE_RUNNING, aeta.selectedTest.state);

  aeta.selectTest(index.getOrAdd('package1.module1'));
  assertEquals(aeta.selectedTest, index.getOrAdd('package1.module1'));
  assertTrue(aeta.selectedTest.element.hasClass('aet-selected'));
  assertEquals('package1.module1', $('#displayed-test-name').text());
  assertEquals(aeta.STATE_RUNNING, aeta.selectedTest.state);
}

function testSetRootElement() {
  aeta.setRootTestElement($('<div>should be gone</div>'));
  aeta.setRootTestElement($('<div>root element</div>'));
  assertEquals('root element', $('#root').children('div').text());
}

function testAddChildElement() {
  parent = $('<div id="parent"></div>');
  child1 = $('<div id="child1"></div>');
  aeta.addChildTestElement(parent, child1, 0);
  assertEquals('child1', parent.find('> ul > li > div').attr('id'));
  child2 = $('<div id="child2"></div>');
  aeta.addChildTestElement(parent, child2, 1);
  assertEquals('child2', parent.find('> ul > li:last-child > div')
                         .attr('id'));
  child3 = $('<div id="child3"></div>');
  aeta.addChildTestElement(parent, child3, 1);
  assertEquals('child3', parent.find('> ul > li:nth-child(2) > div')
                         .attr('id'));
}

function testUpdateTestVisibility() {
  var index = createTestIndex();
  var test = index.getOrAdd('package1');
  aeta.updateTestVisibility(test);
  assertNotEquals('none', test.element.css('display'));
  test.isVisible = false;
  aeta.updateTestVisibility(test);
  assertEquals('none', test.element.css('display'));
  test.isVisible = true;
  aeta.updateTestVisibility(test);
  assertNotEquals('none', test.element.css('display'));
}

function testUpdateDisplayedState() {
  var index = createTestIndex();
  var test = index.getOrAdd('package1');
  aeta.updateDisplayedState(test);
  assertTrue(test.element.hasClass('aet-unstarted'));

  test.state = aeta.STATE_RUNNING;
  aeta.selectedTest = test;
  aeta.updateDisplayedState(test);
  assertFalse(test.element.hasClass('aet-unstarted'));
  assertTrue(test.element.hasClass('aet-running'));
  assertTrue($('#displayed-test-name').hasClass('aet-running'));
  assertEquals('none', $('#run-again').css('display'));

  test.state = aeta.STATE_PASS;
  aeta.updateDisplayedState(test);
  assertFalse(test.element.hasClass('aet-unstarted'));
  assertFalse(test.element.hasClass('aet-running'));
  assertTrue(test.element.hasClass('aet-pass'));
  assertTrue($('#displayed-test-name').hasClass('aet-pass'));
  assertNotEquals('none', $('#run-again').css('display'));

  var test2 = index.getOrAdd('package2');
  test2.state = aeta.STATE_RUNNING;
  aeta.updateDisplayedState(test2);
  assertTrue(test2.element.hasClass('aet-running'));
  assertTrue(test.element.hasClass('aet-pass'));
  assertTrue($('#displayed-test-name').hasClass('aet-pass'));
  assertNotEquals('none', $('#run-again').css('display'));
}

function testUpdateDisplayedOutput() {
  var index = createTestIndex();
  var test = index.getOrAdd('package1');
  test.addMessage('message');
  aeta.updateDisplayedOutput();
  assertEquals('No test selected.', $('#output').text());
  aeta.selectedTest = test;
  aeta.updateDisplayedOutput();
  assertEquals(test.getOutput(), $('#output').text());
}

/**
 * Mocks display-related functions with ones that set global variables instead.
 * The elements that replace jQuery objects have these properties:
 * - {!aeta.TestObject} test The test object this element displays.
 * - {!Array<!Element>} childrenElems A sorted list of child elements.
 * - {string} state The displayed state of the test.
 * - {boolean} isVisible Whether the element is currently visible.
 * The following global variables are exported:
 * - {!Object.<string, Element>} testElements A mapping from test fullname to
 *     its element.
 * - {?string} rootTestName The fullname of the root test, or null if there is
 *     no root.
 */
function mockDisplay() {
  testElements = {};
  rootTestName = null;
  mockProperty(aeta, 'createTestElement', function(obj) {
    elem = {test: obj, childrenElems: [], state: aeta.STATE_RUNNING,
            isVisible: true};
    testElements[obj.fullname] = elem;
    return elem;
  });
  mockProperty(aeta, 'setRootTestElement', function(elem) {
    rootTestName = elem.test.fullname;
  });
  mockProperty(aeta, 'addChildTestElement', function(parent, child, pos) {
    parent.childrenElems.splice(pos, 0, child);
  });
  mockProperty(aeta, 'updateTestVisibility', function(test) {
    test.element.isVisible = test.isVisible;
  });
  mockProperty(aeta, 'updateDisplayedState', function(test) {
    test.element.state = test.state;
  });
}

/**
 * Asserts that a given test has a given state, both in the aeta.TestObject and
 * in its displayed element.
 * @param {string} expState The expected state.
 * @param {!aeta.TestObject} test The test to check the state of.
 */
function assertStateEquals(expState, test) {
  assertEquals(expState, test.state);
  assertEquals(expState, test.element.state);
}

/**
 * Asserts that a given test has a given visibility, both in the
 * aeta.TestObject and in its displayed element.
 * @param {boolean} expVis Whether the test is expected to be visible.
 * @param {!aeta.TestObject} test The test to check the visibility of.
 */
function assertVisibilityEquals(expVis, test) {
  assertEquals(expVis, test.isVisible);
  assertEquals(expVis, test.element.isVisible);
}

// Tests for aeta.TestIndex/aeta.TestObject.

function testCreateRoot() {
  mockDisplay();
  var index = new aeta.TestIndex();
  var root = new aeta.TestObject(index, '', null);
  assertEquals(rootTestName, '');
  assertEquals(root, testElements[''].test);
  assertEquals(0, testElements[''].childrenElems.length);
}

function testGetOrAddFromRoot() {
  var index;
  var expectedParent = null;
  var createdNames = [];
  mockProperty(aeta, 'TestObject', function(ind, fullname, parent) {
    assertEquals(expectedParent, parent);
    expectedParent = this;
    createdNames.push(fullname);
    this.fullname = fullname;
  });
  index = new aeta.TestIndex();
  var method = index.getOrAdd('package.module.Class.method');
  assertEquals('package.module.Class.method', method.fullname);
  assertArrayEquals(['', 'package', 'package.module', 'package.module.Class',
                     'package.module.Class.method'], createdNames);
  createdNames = [];
  var method2 = index.getOrAdd('package.module.Class.method');
  assertEquals(method, method2);
  assertEquals(0, createdNames.length);
  var module = index.getOrAdd('package.module');
  assertEquals('package.module', module.fullname);
  assertEquals(0, createdNames.length);
  expectedParent = module;
  var anotherClass = index.getOrAdd(
    'package.module.AnotherClass.another_method');
  assertArrayEquals(['package.module.AnotherClass',
                     'package.module.AnotherClass.another_method'],
                    createdNames);
  assertEquals('package.module.AnotherClass.another_method',
               anotherClass.fullname);
}

function testGetOrAddFromObject() {
  ROOT_NAME = 'package.subpackage';
  var index;
  var createdNames = [];
  var expectedParent = null;
  mockProperty(aeta, 'TestObject', function(ind, fullname, parent) {
    assertEquals(expectedParent, parent);
    expectedParent = this;
    createdNames.push(fullname);
    this.fullname = fullname;
  });
  index = new aeta.TestIndex();
  var method = index.getOrAdd('package.subpackage.module.Class.method');
  assertEquals('package.subpackage.module.Class.method', method.fullname);
  assertArrayEquals(['package.subpackage', 'package.subpackage.module',
                     'package.subpackage.module.Class',
                     'package.subpackage.module.Class.method'], createdNames);
  createdNames = [];
  var method2 = index.getOrAdd('package.subpackage.module.Class.method');
  assertEquals(method, method2);
  assertEquals(0, createdNames.length);
  var module = index.getOrAdd('package.subpackage.module');
  assertEquals('package.subpackage.module', module.fullname);
  assertEquals(0, createdNames.length);
  expectedParent = module;
  var anotherClass = index.getOrAdd(
    'package.subpackage.module.AnotherClass.another_method');
  assertArrayEquals(['package.subpackage.module.AnotherClass',
                     'package.subpackage.module.AnotherClass.another_method'],
                    createdNames);
  assertEquals('package.subpackage.module.AnotherClass.another_method',
               anotherClass.fullname);
  createdNames = [];
  expectedParent = index.getOrAdd('package.subpackage');
  var module = index.getOrAdd('other.module');
  assertArrayEquals(['other', 'other.module'], createdNames);
}


function testCreateChildren() {
  mockDisplay();
  var index = createTestIndex();
  assertArrayEquals([index.getOrAdd('package1'), index.getOrAdd('package2'),
                     index.getOrAdd('package3')], index.getOrAdd('').children);
  assertArrayEquals([testElements['package1'], testElements['package2'],
                     testElements['package3']],
                    testElements[''].childrenElems);
}

function testForEachContained() {
  mockDisplay();
  var index = createTestIndex();
  var root = index.getOrAdd('');
  var preorder = [];
  root.forEachContained(function(test) { preorder.push(test.fullname); });
  assertArrayEquals(['', 'package1', 'package1.module1',
                     'package1.module1.Class1',
                     'package1.module1.Class1.method1',
                     'package1.module1.Class2',
                     'package1.module1.Class2.method2',
                     'package1.module2', 'package2', 'package3'], preorder);
  var postorder = [];
  root.forEachContained(function(test) { postorder.push(test.fullname); },
                        true);
  assertArrayEquals(['package1.module1.Class1.method1',
                     'package1.module1.Class1',
                     'package1.module1.Class2.method2',
                     'package1.module1.Class2', 'package1.module1',
                     'package1.module2', 'package1', 'package2', 'package3',
                     ''],
                    postorder);
}

function testGetOutput() {
  mockDisplay();
  var index = createTestIndex();
  index.getOrAdd('').setState(aeta.STATE_ERROR);
  index.getOrAdd('').addMessage('root error');
  index.getOrAdd('package1').addMessage('package1 error');
  index.getOrAdd('package1.module2').addMessage('package1.module2 error');
  expOutput = [
    'Error\n',
    'In package1:',
    'package1 error',
    'In package1.module2:',
    'package1.module2 error',
    'In All tests:',
    'root error'
  ].join('\n');
  assertEquals(expOutput, index.getOrAdd('package1').getOutput());
}

function testRecomputeState() {
  mockDisplay();
  var index = createTestIndex();
  index.getOrAdd('').setState(aeta.STATE_PASS);
  index.getOrAdd('package1.module1').state = aeta.STATE_RUNNING;
  aeta.updateDisplayedState(index.getOrAdd('package1.module1'));
  index.getOrAdd('package1').recomputeState();
  assertStateEquals(aeta.STATE_RUNNING, index.getOrAdd('package1.module1'));
  assertStateEquals(aeta.STATE_RUNNING, index.getOrAdd('package1'));
  assertStateEquals(aeta.STATE_RUNNING, index.getOrAdd(''));
  assertStateEquals(aeta.STATE_PASS, index.getOrAdd('package1.module2'));
  assertStateEquals(aeta.STATE_PASS, index.getOrAdd('package2'));
  index.getOrAdd('package1.module1').state = aeta.STATE_ERROR;
  aeta.updateDisplayedState(index.getOrAdd('package1.module1'));
  assertStateEquals(aeta.STATE_ERROR, index.getOrAdd('package1.module1'));
  assertStateEquals(aeta.STATE_RUNNING, index.getOrAdd('package1'));
}

function testSetState() {
  mockDisplay();
  var index = createTestIndex();
  index.getOrAdd('').setState(aeta.STATE_RUNNING);
  assertStateEquals(aeta.STATE_RUNNING, index.getOrAdd(''));
  assertStateEquals(aeta.STATE_RUNNING, index.getOrAdd('package1.module1'));
  assertStateEquals(aeta.STATE_RUNNING, index.getOrAdd('package2'));
  index.getOrAdd('package1').setState(aeta.STATE_PASS);
  assertStateEquals(aeta.STATE_RUNNING, index.getOrAdd(''));
  assertStateEquals(aeta.STATE_PASS, index.getOrAdd('package1'));
  assertStateEquals(aeta.STATE_PASS, index.getOrAdd('package1.module2'));
  assertStateEquals(aeta.STATE_RUNNING, index.getOrAdd('package2'));
  index.getOrAdd('package2').setState(aeta.STATE_FAIL);
  assertStateEquals(aeta.STATE_FAIL, index.getOrAdd('package2'));
  assertStateEquals(aeta.STATE_RUNNING, index.getOrAdd(''));
  index.getOrAdd('package3').setState(aeta.STATE_ERROR);
  assertStateEquals(aeta.STATE_ERROR, index.getOrAdd('package3'));
  assertStateEquals(aeta.STATE_ERROR, index.getOrAdd(''));
  assertStateEquals(aeta.STATE_PASS, index.getOrAdd('package1'));
}

function testRecomputeVisibility() {
  mockDisplay();
  var index = createTestIndex();
  index.visibleStates = [aeta.STATE_ERROR];
  index.getOrAdd('package1.module1.Class1.method1').recomputeVisibility();
  assertVisibilityEquals(false,
                         index.getOrAdd('package1.module1.Class1.method1'));
  assertVisibilityEquals(true, index.getOrAdd('package1.module1.Class1'));
  index.getOrAdd('package1.module1.Class1').recomputeVisibility();
  index.getOrAdd('package1.module1').recomputeVisibility();
  assertVisibilityEquals(false, index.getOrAdd('package1.module1.Class1'));
  assertVisibilityEquals(true, index.getOrAdd('package1.module1'));
  index.getOrAdd('package1.module1.Class2.method2').recomputeVisibility(true);
  assertVisibilityEquals(false,
                         index.getOrAdd('package1.module1.Class2.method2'));
  assertVisibilityEquals(false, index.getOrAdd('package1.module1.Class2'));
  assertVisibilityEquals(false, index.getOrAdd('package1.module1'));
  assertVisibilityEquals(true, index.getOrAdd('package1.module2'));
  assertVisibilityEquals(true, index.getOrAdd('package1'));
}

function testSetStateVisibility() {
  mockDisplay();
  var index = createTestIndex();
  index.visibleStates = [aeta.STATE_UNSTARTED];
  index.getOrAdd('package1.module1').setState(aeta.STATE_RUNNING);
  assertVisibilityEquals(false, index.getOrAdd('package1.module1'));
  assertVisibilityEquals(true, index.getOrAdd('package1'));
  index.getOrAdd('package1.module2').setState(aeta.STATE_RUNNING);
  assertVisibilityEquals(false, index.getOrAdd('package1.module2'));
  assertVisibilityEquals(false, index.getOrAdd('package1'));
  assertVisibilityEquals(true, index.getOrAdd(''));
  index.getOrAdd('').setState(aeta.STATE_ERROR);
  assertVisibilityEquals(false, index.getOrAdd(''));
  assertVisibilityEquals(false, index.getOrAdd('package1'));
  assertVisibilityEquals(false, index.getOrAdd('package1.module1'));
}

function testUpdateVisibility() {
  mockDisplay();
  var index = createTestIndex();
  index.visibleStates = [aeta.STATE_RUNNING];
  index.getOrAdd('package1').updateVisibility();
  assertVisibilityEquals(true, index.getOrAdd(''));
  assertVisibilityEquals(false, index.getOrAdd('package1'));
  assertVisibilityEquals(false, index.getOrAdd('package1.module1'));
  assertVisibilityEquals(true, index.getOrAdd('package2'));
}

function testAddError() {
  mockDisplay();
  var index = createTestIndex();
  index.addError('package1', 'error!');
  assertStateEquals(aeta.STATE_ERROR, index.getOrAdd('package1'));
  assertArrayEquals(['error!'], index.getOrAdd('package1').messages);
  index.addError('package2', 'failure!', aeta.STATE_FAIL);
  assertStateEquals(aeta.STATE_FAIL, index.getOrAdd('package2'));
  assertArrayEquals(['failure!'], index.getOrAdd('package2').messages);
}

function testAddErrors() {
  mockDisplay();
  var index = createTestIndex();
  index.addErrors([['package1.module1', 'some error'],
                   ['package1.module2', 'another error']])
  assertStateEquals(aeta.STATE_ERROR, index.getOrAdd('package1.module1'));
  assertStateEquals(aeta.STATE_ERROR, index.getOrAdd('package1.module2'));
  assertStateEquals(aeta.STATE_ERROR, index.getOrAdd('package1'));
  assertArrayEquals(['some error'],
                    index.getOrAdd('package1.module1').messages);
  assertArrayEquals(['another error'],
                    index.getOrAdd('package1.module2').messages);
  index.addErrors([['package2', 'some failure'],
                   ['package3', 'another failure']], aeta.STATE_FAIL);
  assertStateEquals(aeta.STATE_FAIL, index.getOrAdd('package2'));
  assertStateEquals(aeta.STATE_FAIL, index.getOrAdd('package3'));
  assertStateEquals(aeta.STATE_ERROR, index.getOrAdd(''));
  assertArrayEquals(['some failure'], index.getOrAdd('package2').messages);
  assertArrayEquals(['another failure'], index.getOrAdd('package3').messages);
}

function testRun() {
  mockDisplay();
  var started = false;
  mockProperty(aeta.TestResultUpdater.prototype, 'startBatch', function() {
    assertEquals('package1', this.fullname);
    started = true;
  });
  var index = createTestIndex();
  index.getOrAdd('package1').run();
  assertStateEquals(aeta.STATE_RUNNING, index.getOrAdd('package1'));
  assertTrue(started);
}



// Tests for aeta.TestResultUpdater.

/**
 * Mocks the setTimeout() function to immediately call the function.
 */
function mockSetTimeout() {
  mockProperty(window, 'setTimeout', function(fn, time) { fn(); });
}

BATCH_ID = 1000;

/**
 * Mocks the startBatch() function to immediately succeed with a batch id.
 */
function mockStartBatch() {
  mockProperty(aeta, 'startBatch',
               function(fullname, successCallback, errorCallback) {
                 assertEquals('package1', fullname);
                 successCallback({batch_id: BATCH_ID});
               });
}

BATCH_INFO = {
  num_units: 2,
  test_unit_methods: {
    'package1.module1.Class1': ['package1.module1.Class1.method1'],
    'package1.module1.Class2': ['package1.module1.Class2.method2']
  },
  load_errors: [['package1.module2', 'import error']]
};

/**
 * Mocks the batchInfo() function to first return no information and then
 * eventually succeed, returning BATCH_INFO.
 */
function mockBatchInfo() {
  var timesCalled = 0;
  mockProperty(
    aeta, 'batchInfo', function(batchId, successCallback, errorCallback) {
      assertEquals(BATCH_ID, batchId);
      ++timesCalled;
      if (timesCalled < 3) {
        successCallback(null);
      } else if (timesCalled == 3) {
        successCallback(BATCH_INFO);
      } else {
        fail('Too many calls to batchInfo');
      }
    });
}

BATCH_RESULTS = [
  {'fullname': 'package1.module1.Class1',
   'load_errors': [],
   'errors': [['package1.module1.Class1.method1', 'error!']],
   'failures': [],
   'output': ''},
  {'fullname': 'package1.module1.Class2',
   'load_errors': [],
   'errors': [],
   'failures': [],
   'output': 'some output'}
];

/**
 * Mocks the batchResults() function to return gradually increasing subarrays
 * of BATCH_RESULTS.
 */
function mockBatchResults() {
  var timesCalled = 0;
  function batchResults(batchId, start, successCallback, errorCallback) {
    assertEquals(BATCH_ID, batchId);
    // Have 0 results the first time called, 1 the next time, etc.
    var result = BATCH_RESULTS.slice(start, timesCalled);
    ++timesCalled;
    successCallback(result);
  }
  mockProperty(aeta, 'batchResults', batchResults);
}

function testStartBatch() {
  mockDisplay();
  var index = createTestIndex();
  var updater = new aeta.TestResultUpdater(index, 'package1');
  var batchId = 1000;
  var timesInitialized = 0;
  mockStartBatch();
  mockProperty(aeta.TestResultUpdater.prototype, 'initializeBatchInfo',
               function() {
    assertEquals(batchId, updater.batchId);
    ++timesInitialized;
  });
  updater.startBatch();
  assertEquals(1, timesInitialized);
  // It should only start once.
  updater.startBatch();
  assertEquals(1, timesInitialized);
}

function testUpdateBatchInfo() {
  mockDisplay();
  var index = createTestIndex();
  aeta.selectedTest = index.getOrAdd('package1');
  var updater = new aeta.TestResultUpdater(index, 'package1');
  updater.updateBatchInfo(BATCH_INFO);
  assertStateEquals(aeta.STATE_ERROR, index.getOrAdd('package1.module2'));
  assertEquals(BATCH_INFO.num_units, updater.numUnits);
  for (var unit in BATCH_INFO.test_unit_methods) {
    assertArrayEquals(BATCH_INFO.test_unit_methods[unit],
                      updater.testUnitMethods[unit]);
  }
  assertTrue($('#output').text().indexOf('import error') != -1);
}

function testUpdateResults() {
  mockDisplay();
  var index = createTestIndex();
  aeta.selectedTest = index.getOrAdd('package1');
  var updater = new aeta.TestResultUpdater(index, 'package1');
  updater.updateBatchInfo(BATCH_INFO);
  updater.updateResults(BATCH_RESULTS);
  assertStateEquals(aeta.STATE_ERROR,
                    index.getOrAdd('package1.module1.Class1.method1'));
  assertStateEquals(aeta.STATE_PASS,
                    index.getOrAdd('package1.module1.Class2.method2'));
  assertArrayEquals(['some output'],
                    index.getOrAdd('package1.module1.Class2').messages);
  assertTrue($('#output').text().indexOf('error!') != -1);
}

/**
 * Mocks the updateBatchInfo() and updateResults() methods.
 * @return {{updateBatchInfo: boolean, updatedResults: boolean}} A tracker
 *     object whose fields will be set to true when the appropriate methods are
 *     called with the correct arguments.
 */
function mockUpdateBatch() {
  var tracker = {updatedBatchInfo: false, updatedResults: false};
  var origUpdateBatchInfo = aeta.TestResultUpdater.prototype.updateBatchInfo;
  mockProperty(aeta.TestResultUpdater.prototype, 'updateBatchInfo',
    function(info) {
      assertEquals(JSON.stringify(BATCH_INFO), JSON.stringify(info));
      origUpdateBatchInfo.call(this, info);
      tracker.updatedBatchInfo = true;
    });

  var origUpdateResults = aeta.TestResultUpdater.prototype.updateResults;
  var numDone = 0;
  mockProperty(aeta.TestResultUpdater.prototype, 'updateResults',
    function(results) {
      for (var i = 0; i < results.length; ++i) {
        assertEquals(JSON.stringify(BATCH_RESULTS[numDone + i]),
                     JSON.stringify(results[i]));
      }
      origUpdateResults.call(this, results);
      numDone += results.length;
      if (numDone == BATCH_RESULTS.length) {
        tracker.updatedResults = true;
      }
    });
  return tracker;
}

function testStartBatchImmediate() {
  mockDisplay();
  var index = createTestIndex();
  var updater = new aeta.TestResultUpdater(index, 'package1');
  mockProperty(aeta, 'startBatch',
               function(fullname, successCallback, errorCallback) {
                 assertEquals('package1', fullname);
                 successCallback({
                   batch_info: BATCH_INFO, results: BATCH_RESULTS});
               });
  var tracker = mockUpdateBatch();
  updater.startBatch();
  assertTrue(tracker.updatedBatchInfo);
  assertTrue(tracker.updatedResults);
}

function testStartBatchError() {
  mockDisplay();
  var index = createTestIndex();
  var updater = new aeta.TestResultUpdater(index, 'package1');
  mockProperty(aeta, 'startBatch', function(fullname, succ, err) {
    err('some error');
  });
  updater.startBatch();
  assertStateEquals(aeta.STATE_ERROR, index.getOrAdd('package1'));
  assertArrayEquals(['some error'], index.getOrAdd('package1').messages);
}

function testInitializeBatch() {
  mockDisplay();
  var index = createTestIndex();
  var updater = new aeta.TestResultUpdater(index, 'package1');
  mockSetTimeout();
  mockStartBatch();
  mockBatchInfo();
  var tracker = mockUpdateBatch();
  var polled = false;
  mockProperty(aeta.TestResultUpdater.prototype, 'pollResults', function() {
    assertTrue(tracker.updatedBatchInfo);
    polled = true;
  });
  updater.startBatch();
  assertTrue(polled);
}

function testPollResults() {
  mockDisplay();
  var index = createTestIndex();
  var updater = new aeta.TestResultUpdater(index, 'package1');
  var timesCalled = 0;
  index.getOrAdd('package1').setState(aeta.STATE_RUNNING);
  mockSetTimeout();
  mockStartBatch();
  mockBatchInfo();
  mockBatchResults();
  var tracker = mockUpdateBatch();
  updater.startBatch();
  assertTrue(tracker.updatedResults);
}

function testInitializeTests() {
  mockDisplay();
  mockProperty(aeta, 'getMethods', function(fullname, success, error) {
    assertEquals(ROOT_NAME, fullname);
    success({
      method_names: [
        'package1.module1.Class1.method1',
        'package1.module1.Class1.method2',
        'package1.module1.Class2.method3'
      ],
      load_errors: [['package1.module2', 'import error']]
    });
  });
  aeta.testIndex = new aeta.TestIndex();
  aeta.initializeTests();
  // Make sure everything is displayed.
  assertNotUndefined(testElements['']);
  assertNotUndefined(testElements['package1']);
  assertNotUndefined(testElements['package1.module1']);
  assertNotUndefined(testElements['package1.module1.Class1']);
  assertNotUndefined(testElements['package1.module1.Class1.method1']);
  assertNotUndefined(testElements['package1.module1.Class1.method2']);
  assertNotUndefined(testElements['package1.module1.Class2']);
  assertNotUndefined(testElements['package1.module1.Class2.method3']);
  assertNotUndefined(testElements['package1.module2']);
  // Make sure load errors are recorded.
  assertArrayEquals(['import error'],
                    aeta.testIndex.getOrAdd('package1.module2').messages);
  // Should have hid "Loading..." text.
  assertEquals('none', $('#loading').css('display'));
}

function testUpdateVisibleStates() {
  mockDisplay();
  aeta.testIndex = new aeta.TestIndex();
  $('#show-unstarted').attr('checked', false);
  $('#show-running').attr('checked', false);
  var updated = false;
  mockProperty(aeta.testIndex.root, 'updateVisibility', function() {
    updated = true;
    aeta.testIndex.visibleStates.sort();
    var expVisible = [aeta.STATE_FAIL, aeta.STATE_ERROR, aeta.STATE_PASS];
    expVisible.sort();
    assertArrayEquals(expVisible, aeta.testIndex.visibleStates);
  });
  aeta.updateVisibleStates();
  assertTrue(updated);
}
