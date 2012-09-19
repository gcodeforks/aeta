#!/usr/bin/env python
#
# Copyright 2011 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


"""Tests for gaedriver."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

# pylint: disable-msg=C0111,C0103,W0613,W0212,W0232,W0603,E1101,F0401

import os
import signal
import unittest

from pyfakefs import fake_filesystem
from pyfakefs import fake_filesystem_shutil

import gaedriver

# Some test flags which can be used for testing gaedriver.
GAEDRIVER_TEST_FLAGS = {'app_id': 'example-id',
                        'backend_id': 'backend-id',
                        'backend_instances': 5,
                        'cluster_hostname': 'appspot.com',
                        'username': 'alice@example.com',
                        'password': 'secret',
                        'sdk_dir': '/path/to/sdk',
                        'app_dir': '/path/to/app',
                        }

GENERIC_APPCFG_ERROR_MSG = 'Error: Something went wrong.'


def mock_run_appcfg_with_auth_no_error(*args, **kwargs):
    return ('Everything is fine.', 'stderr')


def mock_run_appcfg_with_auth_with_error(*args, **kwargs):
    return (GENERIC_APPCFG_ERROR_MSG, 'stderr')


def get_test_config(attributes=None, del_attr=None):
    """Get an initialized gaedriver.Config instance.

    The instance will have a number of default values already set,
    unless you explicitely change or remove them

    Args:
      attributes: A dict of default attribute values.
      del_attr: Attributes which should explicitely not be set.

    Returns:
      A gaedriver.Config instance.
    """
    all_attributes = dict(GAEDRIVER_TEST_FLAGS)
    if del_attr is None:
        del_attr = []
    if attributes is None:
        attributes = {}
    all_attributes.update(attributes)
    for attr in del_attr:
        del all_attributes[attr]
    # pylint: disable-msg=W0142
    return gaedriver.Config(**all_attributes)


class IsClusterAppserverTest(unittest.TestCase):
    """Tests for is_cluster_appserver."""

    def test_invalid_input(self):
        invalid_input = [None, 0, (), [], {}]
        for invalid in invalid_input:
            self.assertRaises(TypeError,
                              gaedriver.is_cluster_appserver, invalid)

    def test_dev_appserver(self):
        inputs = ['localhost',
                  'localhost:8080']
        for cluster_hostname in inputs:
            self.assertFalse(gaedriver.is_cluster_appserver(cluster_hostname))

    def test_appserver(self):
        inputs = ['example.com',
                  'something.example.com',
                  'example.appspot.com',
                  ]
        for cluster_hostname in inputs:
            self.assertTrue(gaedriver.is_cluster_appserver(cluster_hostname))


# pylint: disable-msg=R0902,R0904,
class ConfigTest(unittest.TestCase):
    """Tests for the Config class."""

    def setUp(self):
        self.app_id = 'appid'
        self.backend_id = 'backendid'
        self.backend_instances = 5
        self.cluster_hostname = 'appspot.com'
        self.sdk_dir = '/path/to/sdk'
        self.app_dir = '/path/to/app_dir'
        self.username = 'alice@example.com'
        self.password = 'secret'
        self.appcfg_flags = '--runtime=python27 -R'

    def test_invalid_args(self):
        # Test that invalid input is not accepted.
        self.assertRaises(TypeError, gaedriver.Config, None,
                          self.cluster_hostname)
        self.assertRaises(TypeError, gaedriver.Config, self.app_id, None)
        self.assertRaises(TypeError, gaedriver.Config, None, None)

    def test_default(self):
        # Test the minimum set of required arguments.
        config = gaedriver.Config(self.app_id, self.cluster_hostname)
        self.assertEqual(self.app_id, config.app_id)
        self.assertEqual(self.cluster_hostname, config.cluster_hostname)
        self.assertEqual('', config.backend_id)
        self.assertEqual(0, config.backend_instances)
        self.assertEqual('', config.domain)
        self.assertEqual('', config.partition)
        self.assertEqual('', config.sdk_dir)
        self.assertEqual('', config.app_dir)
        self.assertEqual('', config.username)
        self.assertEqual('', config.password)
        self.assertEqual('', config.appcfg_flags)

    def test_backend_for_appserver(self):
        # Test construction of hostnames for tests against appserver.

        conf = gaedriver.Config(self.app_id, self.cluster_hostname,
                                backend_id=self.backend_id)
        expected_hostname = '%s.%s.%s' % (self.backend_id, self.app_id,
                                          self.cluster_hostname)
        self.assertEqual(expected_hostname, conf.app_hostname)

    def test_backend_instances(self):
        conf = gaedriver.Config(self.app_id, self.cluster_hostname,
                                backend_instances=self.backend_instances)
        self.assertEqual(self.backend_instances, conf.backend_instances)

    def test_hostname_for_appserver(self):
        # Test construction of hostnames for tests against appserver.
        conf = gaedriver.Config(self.app_id, self.cluster_hostname)
        self.assertEqual('%s.%s' % (self.app_id, self.cluster_hostname),
                         conf.app_hostname)

    def test_hostname_for_dev_appserver(self):
        # Test construction of hostnames for tests against dev_appserver.
        self.cluster_hostname = 'localhost:8080'
        conf = gaedriver.Config(self.app_id, self.cluster_hostname)
        self.assertEqual(self.cluster_hostname, conf.app_hostname)
        self.assertEqual(gaedriver.NO_ADMIN_CONSOLE_ON_SDK,
                         conf.ac_hostname)

    def test_partition(self):
        # Test construction of the application domain.
        appid_partition_tuples = [('foo', ''),
                                  ('gmail.com:foo', ''),
                                  ('s~foo', 's'),
                                  ('s~alpha:bar', 's'),
                                                         ]
        for app_id, partition in appid_partition_tuples:
            conf = gaedriver.Config(app_id, self.cluster_hostname)
            self.assertEqual(partition, conf.partition)

    def test_domain(self):
        # Test construction of the application domain.
        appid_domain_tuples = [('foo', ''),
                               ('gmail.com:foo', 'gmail.com'),
                               ('s~gmail.com:foo', 'gmail.com'),
                               ('alpha:bar', 'alpha'),
                               ]
        for app_id, domain in appid_domain_tuples:
            conf = gaedriver.Config(app_id, self.cluster_hostname)
            self.assertEqual(domain, conf.domain)

    def test_display_appid(self):
        # Test construction of the application domain.
        appid_displayappid_tuples = [('foo', 'foo'),
                                     ('gmail.com:foo', 'foo'),
                                     ('s~foo', 'foo'),
                                     ('s~alpha:bar', 'bar'),
                                     ]
        for app_id, display_app_id in appid_displayappid_tuples:
            conf = gaedriver.Config(app_id, self.cluster_hostname)
            self.assertEqual(display_app_id, conf.display_app_id)

    def test_admin_console_hostname(self):
        # Test construction of the admin console hostname.
        conf = gaedriver.Config(self.app_id, self.cluster_hostname)
        self.assertEqual('appengine.google.com', conf.ac_hostname)
        conf = gaedriver.Config(self.app_id, self.cluster_hostname,
                                ac_hostname='example.com')
        self.assertEqual('example.com', conf.ac_hostname)

    def test_appcfg_flags(self):
        # Test construction of the extra appcfg flags.
        conf = gaedriver.Config(self.app_id, self.cluster_hostname,
                                appcfg_flags=self.appcfg_flags)
        self.assertEqual(self.appcfg_flags, conf.appcfg_flags)


class LoadConfigFromFileTest(unittest.TestCase):
    """Tests for GetConfigCopy."""

    def setUp(self):
        self.fake_fs = fake_filesystem.FakeFilesystem()
        self.fake_open = fake_filesystem.FakeFileOpen(self.fake_fs)
        self.default_config_dict = {'app_id': 'my-app-id',
                                    'cluster_hostname': 'appspot.com',
                                    'backend_id': 'my-backend',
                                    'backend_instances': '5',
                                    'sdk_dir': '/path/to/sdk',
                                    'app_dir': '/path/to/app',
                                    'username': 'alice@example.com',
                                    'password': 'secret',
                                    'ac_hostname': 'appspot.com',
                                    'appcfg_flags': '--runtime=python27 -R',
                                    }

    # pylint: disable-msg=R0201
    def create_config_content(self, sections):
        lines = []
        for section_name, options in sections.items():
            lines.append('[%s]' % section_name)
            for key, value in options.items():
                lines.append('%s:%s' % (key, value))
        return os.linesep.join(lines)

    def load_config(self, file_content, file_name='config.cfg', index=0):
        config_file_path = file_name
        self.fake_fs.CreateFile(config_file_path, contents=file_content)
        return gaedriver.load_config_from_file(config_file_path,
                                               index=index,
                                               _open_fct=self.fake_open)

    def test_default(self):
        sections = {'config': self.default_config_dict}
        config_content = self.create_config_content(sections)
        config = self.load_config(config_content)
        self.assertEqual('my-app-id', config.app_id)
        self.assertEqual('appspot.com', config.cluster_hostname)
        self.assertEqual('my-backend', config.backend_id)
        self.assertEqual('5', config.backend_instances)
        self.assertEqual('/path/to/sdk', config.sdk_dir)
        self.assertEqual('/path/to/app', config.app_dir)
        self.assertEqual('alice@example.com', config.username)
        self.assertEqual('secret', config.password)
        self.assertEqual('appspot.com', config.ac_hostname)
        self.assertEqual('--runtime=python27 -R', config.appcfg_flags)

    def test_missing_required_args(self):
        for arg in gaedriver.REQUIRED_CONFIG_OPTIONS:
            options = dict(self.default_config_dict)
            del options[arg]
            sections = {'config': options}
            config_content = self.create_config_content(sections)
            self.assertRaises(ValueError, self.load_config, config_content,
                              file_name='%s.cfg' % arg)

    def test_multiple_configs(self):
        input_config1 = dict(self.default_config_dict)
        input_config1['app_id'] = 'my-first-app-id'
        input_config2 = dict(self.default_config_dict)
        input_config2['app_id'] = 'my-second-app-id'
        sections = {'config1': input_config1,
                    'config2': input_config2}
        content = self.create_config_content(sections)
        config_file_path = 'config-file.cfg'
        self.fake_fs.CreateFile(config_file_path, contents=content)
        returned_config = gaedriver.load_config_from_file(
            config_file_path,
            _open_fct=self.fake_open)
        self.assertEqual('my-first-app-id', returned_config.app_id)
        returned_config1 = gaedriver.load_config_from_file(
            config_file_path,
            index=0,
            _open_fct=self.fake_open)
        self.assertEqual('my-first-app-id', returned_config1.app_id)
        returned_config2 = gaedriver.load_config_from_file(
            config_file_path,
            index=1,
            _open_fct=self.fake_open)
        self.assertEqual('my-second-app-id', returned_config2.app_id)

    def test_index_too_high(self):
        sections = {'config': self.default_config_dict}
        config_content = self.create_config_content(sections)
        self.assertRaises(IndexError, self.load_config, config_content, index=3)


class BackendsYamlFileModificationTest(unittest.TestCase):
    """Tests for _create_backends_yaml() and _restore_backends_yaml()."""

    def setUp(self):
        self.orig_os = gaedriver.os
        # has required member - pylint: disable-msg=E1101
        self.orig_open = gaedriver.__builtins__['open']
        self.orig_shutil = gaedriver.shutil
        orig_backend_id = 'backend-id'
        orig_instances = 4
        test_backend_id = 'backend-id'
        test_instances = 6
        self.app_dir = '/path/to/app'
        self.orig_yaml_path = os.path.join(self.app_dir, 'backends.yaml')
        self.backup_yaml_path = os.path.join(self.app_dir, 'backends.yaml.e2e')
        self.orig_content = self.get_backend_yaml_content(orig_backend_id,
                                                          orig_instances)
        self.test_content = self.get_backend_yaml_content(test_backend_id,
                                                          test_instances)
        self.test_config = get_test_config(
            {'app_id': 'appid',
             'app_dir': self.app_dir,
             'backend_id': test_backend_id,
             'backend_instances': test_instances})
        self.fake_fs = fake_filesystem.FakeFilesystem()
        # os and shutil modules have to be replaced explicitely, because
        # gaedriver referenced them when being loaded.
        self.fake_file_mod = fake_filesystem.FakeFileOpen(self.fake_fs)
        self.fake_os_mod = fake_filesystem.FakeOsModule(self.fake_fs)
        gaedriver.os = self.fake_os_mod
        # has required member - pylint: disable-msg=E1101
        gaedriver.__builtins__['open'] = fake_filesystem.FakeFileOpen(
            self.fake_fs)
        gaedriver.shutil = fake_filesystem_shutil.FakeShutilModule(self.fake_fs)

    def tearDown(self):
        gaedriver.os = self.orig_os
        # has required member - pylint: disable-msg=E1101
        gaedriver.__builtins__['open'] = self.orig_open
        gaedriver.shutil = self.orig_shutil

    # pylint: disable-msg=R0201
    def get_backend_yaml_content(self, backend_id, instances):
        lines = []
        lines.append('backends:')
        lines.append('- name: %s' % backend_id)
        lines.append('  options: public, dynamic')
        lines.append('  instances: %s' % instances)
        return os.linesep.join(lines)

    def test_create_backends_yaml(self):
        # create original backends.yaml in a fake filesystem
        self.fake_fs.CreateFile(self.orig_yaml_path, contents=self.orig_content)
        # Test that before running the test we have the original content.
        self.assertEqual(self.orig_content,
                         self.fake_file_mod(self.orig_yaml_path).read())
        gaedriver._create_backends_yaml(self.test_config)
        # and afterwards a backup file was created,
        self.assertTrue(self.fake_os_mod.path.exists(self.backup_yaml_path))
        # having the content of the original file.
        self.assertEqual(self.orig_content,
                         self.fake_file_mod(self.backup_yaml_path).read())
        # Also test that the original was replaced with new content.
        self.assertTrue(self.fake_os_mod.path.exists(self.orig_yaml_path))
        self.assertEqual(self.test_content,
                         self.fake_file_mod(self.orig_yaml_path).read())

    def test_restore_backends_yaml(self):
        # Create original backends.yaml.
        self.fake_fs.CreateFile(self.orig_yaml_path, contents=self.test_content)
        # Create backup backends.yaml.
        self.fake_fs.CreateFile(self.backup_yaml_path,
                                contents=self.orig_content)
        # Test that before running the test we have the original content.
        self.assertEqual(self.test_content,
                         self.fake_file_mod(self.orig_yaml_path).read())
        gaedriver._restore_backends_yaml(self.test_config)
        # and afterwards the backup file was removed.
        self.assertFalse(self.fake_os_mod.path.exists(self.backup_yaml_path))
        # Also test that the backends.yaml was replaced with its original
        # content.
        self.assertTrue(self.fake_os_mod.path.exists(self.orig_yaml_path))
        self.assertEqual(self.orig_content,
                         self.fake_file_mod(self.orig_yaml_path).read())


class RunAppcfgWithAuthTest(unittest.TestCase):
    """Tests for RunAppcfgWithAuth."""

    def test_missing_config_parameter(self):
        # Test behavior for missing configuration parameter.
        for missing_param in ['app_dir', 'sdk_dir', 'username', 'password']:
            config = get_test_config({missing_param: ''})
            self.assertRaises(ValueError, gaedriver.update_app, config)


class UpdateAppTest(unittest.TestCase):
    """Tests for RunAppcfgWithAuth."""

    def setUp(self):
        self.orig_run_appcfg_with_auth = gaedriver.run_appcfg_with_auth
        self.counter = 0

    def tearDown(self):
        gaedriver.run_appcfg_with_auth = self.orig_run_appcfg_with_auth

    def test_missing_config_parameter(self):
        # test behavior for missing configuration parameter.
        gaedriver.run_appcfg_with_auth = lambda c, o, a, args: ('', '')
        for missing_param in ['app_dir', 'username']:
            config = get_test_config({missing_param: ''})
            self.assertRaises(ValueError, gaedriver.update_app, config)

    def test_update_just_works(self):

        # it's okay to not use all arguments, here - pylint: disable-msg=W0613
        def mock_run_appcfg_with_auth(config, action, options=None, args=None):
            self.counter += 1
            return ('', '')

        gaedriver.run_appcfg_with_auth = mock_run_appcfg_with_auth
        config = get_test_config()
        gaedriver.update_app(config)
        self.assertEqual(1, self.counter)

    def test_runs_rollback(self):
        user_email = 'alice@example.com'
        user_name = 'alice'
        err_msg = gaedriver.ROLLBACK_ERR_MESSAGE % user_name
        stdout = 'some prefix %s some suffix' % err_msg

        # it's okay to not use all arguments, here - pylint: disable-msg=W0613
        def mock_run_appcfg_with_auth(config, action, options=None, b=False,
                                                            args=None):
            if action == 'update':
                self.counter += 1
                return (stdout, '')
            elif action == 'rollback':
                return ('done', '')

        gaedriver.run_appcfg_with_auth = mock_run_appcfg_with_auth
        config = get_test_config({'username': user_email})
        gaedriver.update_app(config)
        self.assertEqual(gaedriver.MAX_ROLLBACK_RETRIES, self.counter)

    def test_raises_error_if_rollback_fails(self):
        user_email = 'alice@example.com'
        user_name = 'alice'
        err_msg = gaedriver.ROLLBACK_ERR_MESSAGE % user_name
        stdout = 'some prefix %s some suffix' % err_msg

        # it's okay to not use all arguments, here - pylint: disable-msg=W0613
        def mock_run_appcfg_with_auth(c, action, config=None, b=False,
                                      args=None):
            if action == 'update':
                return (stdout, '')
            elif action == 'rollback':
                return (GENERIC_APPCFG_ERROR_MSG, '')

        gaedriver.run_appcfg_with_auth = mock_run_appcfg_with_auth
        config = get_test_config({'username': user_email})
        self.assertRaises(gaedriver.AppcfgError,
                          gaedriver.update_app, config)

    def test_raises_error_if_update_fails_due_to_something_else(self):
        user_email = 'alice@example.com'

        # it's okay to not use all arguments, here - pylint: disable-msg=W0613
        def mock_run_appcfg_with_auth(c, a, options=None, b=False, args=None):
            self.counter += 1
            return (GENERIC_APPCFG_ERROR_MSG, '')

        gaedriver.run_appcfg_with_auth = mock_run_appcfg_with_auth
        config = get_test_config({'username': user_email})
        self.assertRaises(gaedriver.AppcfgError, gaedriver.update_app,
                          config)
        self.assertEqual(1, self.counter)


class DevAppServerThreadTest(unittest.TestCase):

    def setUp(self):
        self.orig_os = gaedriver.os
        self.orig_fileinput_os = gaedriver.os
        self.orig_shutil = gaedriver.shutil
        self.orig_time = gaedriver.time
        self.orig_threading = gaedriver.threading
        self.orig_builtins_open = __builtins__['open']

    def tearDown(self):
        gaedriver.os = self.orig_os
        gaedriver.fileinput.os = self.orig_fileinput_os
        gaedriver.shutil = self.orig_shutil
        gaedriver.time = self.orig_time
        gaedriver.threading = self.orig_threading
        __builtins__['open'] = self.orig_builtins_open

    # pylint: disable-msg=R0201
    def get_app_yaml_content(self, app_id):
        """Get the content of a typical app.yaml file."""
        lines = []
        lines.append('application: %s' % app_id)
        lines.append('version: 1')
        lines.append('runtime: python')
        lines.append('api_version: 1')
        lines.append('')
        lines.append('handlers:')
        lines.append('- url: .*')
        lines.append('  script: main.py')
        lines.append('')
        lines.append('builtins:')
        lines.append('- remote_api: on')
        lines.append('')
        return os.linesep.join(lines)

    def test_thread_init(self):
        config = get_test_config()
        dev_thread = gaedriver.DevAppServerThread(config)
        self.assertEqual(os.path.join(config.app_dir, 'app.yaml'),
                         dev_thread.app_yaml_path)
        self.assertEqual(os.path.join(config.app_dir,
                                      gaedriver.APP_YAML_BACKUP),
                         dev_thread.app_yaml_bak_path)

    def test_get_argv_bad_app_hostname(self):
        config = get_test_config()
        dev_thread = gaedriver.DevAppServerThread(config)
        config.app_hostname = 'something:with:3:colons'
        self.assertRaises(ValueError, dev_thread._get_argv)
        config.app_hostname = 'something:with:2colons'
        self.assertRaises(ValueError, dev_thread._get_argv)

    def test_get_argv_port_option(self):
        config = get_test_config(attributes={'cluster_hostname':
                                             'localhost:8080'})
        dev_thread = gaedriver.DevAppServerThread(config)
        argv = dev_thread._get_argv()
        self.assertEqual(os.path.join(config.sdk_dir, 'dev_appserver.py'),
                         argv[0])
        # Default port is used
        self.assertTrue('--port=8080' in argv)
        # no port is set when cluster hostname doesn't have a port.
        config = get_test_config(attributes={'cluster_hostname': 'localhost'})
        dev_thread = gaedriver.DevAppServerThread(config)
        argv = dev_thread._get_argv()
        for arg in argv:
            self.assertFalse(arg.startswith('--port'))

    def test_get_argv_other_options(self):
        config = get_test_config()
        options = ['--foo', '--bar']
        dev_thread = gaedriver.DevAppServerThread(config, options)
        argv = dev_thread._get_argv()
        for option in options:
            self.assertTrue(option in argv)

    def test_get_argv_respects_clear_datastore(self):
        config = get_test_config()
        dev_thread = gaedriver.DevAppServerThread(config)
        argv = dev_thread._get_argv()
        self.assertTrue('--clear_datastore' in argv)
        dev_thread = gaedriver.DevAppServerThread(config,
                                                  clear_datastore=False)
        argv = dev_thread._get_argv()
        self.assertTrue('--clear_datastore' not in argv)

    def test_replace_app_yaml(self):
        # Create fake file system.
        fake_fs = fake_filesystem.FakeFilesystem()
        fake_os = fake_filesystem.FakeOsModule(fake_fs)
        fake_open = fake_filesystem.FakeFileOpen(fake_fs)
        fake_shutil_module = fake_filesystem_shutil.FakeShutilModule(fake_fs)
        __builtins__['open'] = fake_open
        gaedriver.fileinput.os = fake_os
        gaedriver.shutil = fake_shutil_module
        # Setup fake app.yaml.
        app_dir = '/path/to/app'
        app_yaml_path = os.path.join(app_dir, 'app.yaml')
        orig_app_id = 'original-app-id'
        test_app_id = 'test-app-id'
        orig_app_yaml_content = self.get_app_yaml_content(orig_app_id)
        new_app_yaml_content = self.get_app_yaml_content(test_app_id)
        config = get_test_config({'app_id': test_app_id, 'app_dir': app_dir})
        fake_fs.CreateFile(app_yaml_path, contents=orig_app_yaml_content)
        # Execute _replace_app_yaml and make sure the modified file
        # looks like original file except for the application ID.
        dev_thread = gaedriver.DevAppServerThread(config)
        dev_thread._replace_app_yaml()
        self.assertEqual(new_app_yaml_content,
                         fake_open(app_yaml_path).read())

    def test_restore_app_yaml(self):
        app_dir = '/path/to/app'
        orig_app_id = 'original-app-id'
        orig_app_yaml_content = self.get_app_yaml_content(orig_app_id)
        test_app_id = 'test-app-id'
        test_app_yaml_content = self.get_app_yaml_content(test_app_id)
        app_yaml_path = os.path.join(app_dir, 'app.yaml')
        app_yaml_bak_path = os.path.join(app_dir, 'app.yaml.e2e')
        config = get_test_config({'app_id': orig_app_id, 'app_dir': app_dir})
        # create original and backup app.yaml in a fake filesystem
        filesystem = fake_filesystem.FakeFilesystem()
        filesystem.CreateFile(app_yaml_path, contents=test_app_yaml_content)
        filesystem.CreateFile(app_yaml_bak_path, contents=orig_app_yaml_content)
        # os and shutil modules have to be replaced explicitely, because
        # gaedriver referenced them when being loaded.
        fake_os_module = fake_filesystem.FakeOsModule(filesystem)
        gaedriver.os = fake_os_module
        fake_shutil_module = fake_filesystem_shutil.FakeShutilModule(filesystem)
        gaedriver.shutil = fake_shutil_module
        fake_file_module = fake_filesystem.FakeFileOpen(filesystem)
        # Test that before running the test we have the replaced content.
        self.assertEqual(test_app_yaml_content,
                         fake_file_module(app_yaml_path).read())

        dev_thread = gaedriver.DevAppServerThread(config)
        dev_thread._restore_app_yaml()

        self.assertFalse(fake_os_module.path.exists(app_yaml_bak_path))
        self.assertTrue(fake_os_module.path.exists(app_yaml_path))
        self.assertEqual(orig_app_yaml_content,
                         fake_file_module(app_yaml_path).read())


    # pylint: disable-msg=W0201
    def test_start(self):
        config = get_test_config()
        dev_thread = gaedriver.DevAppServerThread(config)
        self.replace_app_yaml_called = False
        self.thread_started = False
        self.time_sleep_called = False

        def mock_replace_app_yaml():
            self.replace_app_yaml_called = True

        def mock_thread_start(_):
            self.thread_started = True

        def mock_time_sleep(_):
            self.time_sleep_called = True

        dev_thread._replace_app_yaml = mock_replace_app_yaml
        gaedriver.threading.Thread.start = mock_thread_start
        gaedriver.time.sleep = mock_time_sleep
        dev_thread.start()
        self.assertTrue(self.replace_app_yaml_called)
        # self.assertTrue(self.thread_started)
        self.assertTrue(self.time_sleep_called)

    def test_stop(self):
        config = get_test_config()
        dev_thread = gaedriver.DevAppServerThread(config)

        self.kill_invoked = False
        self.kill_signal = None
        self.restore_app_yaml_called = False

        def mock_kill(_, sig):
            self.kill_invoked = True
            self.kill_signal = sig

        def mock_restore_app_yaml():
            self.restore_app_yaml_called = True

        gaedriver.os.kill = mock_kill
        dev_thread._restore_app_yaml = mock_restore_app_yaml
        # No thread started, so nothing to kill.
        dev_thread.stop()
        self.assertFalse(self.kill_invoked)
        self.assertTrue(self.restore_app_yaml_called)
        # Let's test with a running thread.
        dev_thread.pid = 65000
        self.kill_invoked = False
        self.restore_app_yaml_called = False
        dev_thread.stop()
        self.assertTrue(self.kill_invoked)
        self.assertEqual(signal.SIGKILL, self.kill_signal)
        self.assertTrue(self.restore_app_yaml_called)


# unused arguments are okay for this class - pylint: disable-msg=W0613
class SetUpAppTest(unittest.TestCase):
    """Tests for setup_app."""

    def setUp(self):
        self.orig_devappserver_thread = gaedriver.DevAppServerThread
        self.orig_run_appcfg_with_auth = gaedriver.run_appcfg_with_auth
        self.orig_update_app = gaedriver.update_app
        self.orig_create_backends_yaml = gaedriver._create_backends_yaml

        # pylint: disable-msg=R0903
        class DevAppServerThreadMock(object):

            def __init__(self, _):
                self.started = False

            def start(self):
                self.started = True

        gaedriver.DevAppServerThread = DevAppServerThreadMock

    def tearDown(self):
        gaedriver.DevAppServerThread = self.orig_devappserver_thread
        gaedriver.run_appcfg_with_auth = self.orig_run_appcfg_with_auth
        gaedriver.update_app = self.orig_update_app
        gaedriver._create_backends_yaml = self.orig_create_backends_yaml

    @staticmethod
    def mock_update_app(_):
        return ('Everything is fine.', 'stderr')

    @staticmethod
    def mock_create_backends_yaml(_):
        pass

    @staticmethod
    def mock_run_appcfg_started(*args, **kwargs):
        """Mock RunAppcfgWithAuth() which says a backend is already started."""
        return ('error: backend is already started.', 'stderr')

    def test_dev_appserver(self):
        config = get_test_config()
        config.cluster_hostname = 'localhost:8080'
        app_token = gaedriver.setup_app(config)
        # gaedriver.setup_app should return the thread object
        self.assertTrue(isinstance(app_token, gaedriver.DevAppServerThread))
        # that has a running thread.
        self.assertTrue(app_token.started)

    def test_appserver(self):
        # Test appserver setup without 'backend_id' configured.
        config = get_test_config(del_attr=['backend_id'])

        gaedriver.update_app = SetUpAppTest.mock_update_app
        config.cluster_hostname = 'example.com'
        self.assertEqual(None, gaedriver.setup_app(config))

        # redefining method is okay - pylint: disable-msg=E0102
        def mock_update_app(_):
            return ('Error in stdout', 'stderr')

        gaedriver.update_app = mock_update_app
        config.cluster_hostname = 'example.com'
        self.assertRaises(AssertionError, gaedriver.setup_app, config)

    def test_appserver_with_backend(self):
        config = get_test_config()

        gaedriver.run_appcfg_with_auth = mock_run_appcfg_with_auth_no_error
        gaedriver.update_app = SetUpAppTest.mock_update_app
        gaedriver._create_backends_yaml = SetUpAppTest.mock_create_backends_yaml
        config.cluster_hostname = 'example.com'
        self.assertEqual(None, gaedriver.setup_app(config))

        gaedriver.run_appcfg_with_auth = SetUpAppTest.mock_run_appcfg_started
        self.assertEqual(None, gaedriver.setup_app(config))

        def mock3_run_appcfg_with_auth(*args, **kwargs):
            return (GENERIC_APPCFG_ERROR_MSG, 'stderr')

        gaedriver.run_appcfg_with_auth = mock3_run_appcfg_with_auth
        self.assertRaises(AssertionError, gaedriver.setup_app, config)


class TearDownAppTest(unittest.TestCase):
    """Tests for teardown_app."""

    def setUp(self):
        self.config = get_test_config()
        self.orig_run_appcfg_with_auth = gaedriver.run_appcfg_with_auth
        self.orig_restore_backends_yaml = gaedriver._restore_backends_yaml

    def tearDown(self):
        gaedriver.run_appcfg_with_auth = self.orig_run_appcfg_with_auth
        gaedriver._restore_backends_yaml = self.orig_restore_backends_yaml

    @staticmethod
    def mock_restore_backends_yaml(_):
        pass

    @staticmethod
    def mock_run_appcfg_stopped(_, action, **kwargs):
        """Mock RunAppcfgWithAuth() which says a backend is already stopped."""
        if action == 'stop':
            return ('error: Backend is already stopped.', 'stderr')
        else:
            return ('Everything is fine.', 'stderr')

    def test_dev_appserver(self):

        # pylint: disable-msg=R0903
        class MockDevAppServerThread(object):

            def __init__(self):
                self.stopped = False

            def stop(self):
                self.stopped = True

        app_token = MockDevAppServerThread()
        self.config.cluster_hostname = 'localhost:8080'
        gaedriver.teardown_app(self.config, app_token)
        self.assertTrue(app_token.stopped)

    def test_appserver_with_backend_no_error(self):
        config = get_test_config()
        mock_restore = TearDownAppTest.mock_restore_backends_yaml
        gaedriver._restore_backends_yaml = mock_restore
        gaedriver.run_appcfg_with_auth = mock_run_appcfg_with_auth_no_error
        self.assertEqual(None, gaedriver.teardown_app(config, None))

    def test_appserver_with_backend_already_stopped(self):
        config = get_test_config()
        mock_restore = TearDownAppTest.mock_restore_backends_yaml
        gaedriver._restore_backends_yaml = mock_restore
        gaedriver.run_appcfg_with_auth = TearDownAppTest.mock_run_appcfg_stopped
        self.assertEqual(None, gaedriver.teardown_app(config, None))

    def test_appserver_with_backend_and_error(self):
        config = get_test_config()
        mock_restore = TearDownAppTest.mock_restore_backends_yaml
        gaedriver._restore_backends_yaml = mock_restore
        gaedriver.run_appcfg_with_auth = mock_run_appcfg_with_auth_with_error
        self.assertRaises(AssertionError, gaedriver.teardown_app, config,
                                            None)
