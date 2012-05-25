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


"""gaedriver - a tool for end-to-end testing of App Engine apps."""

__author__ = 'schuppe@google.com (Robert Schuppenies)'

# pylint: disable-msg=C0111,C0103,W0232,W0603,E1101,F0401

import ConfigParser
import fileinput
import os
import re
import shutil
import signal
import subprocess
import threading
import time

# All options for Config objects (see below).
CONFIG_OPTIONS = {
    'app_id': 'Application ID to use when referring to the application.',
    'cluster_hostname': 'Hostname of the cluster where the app is hosted.',
    'backend_id': 'Backend identifier.',
    'backend_instances': 'Number of available backend instances.',
    'sdk_dir': 'Local directory where the SDK is located.',
    'app_dir': 'Local directory where the application is located.',
    'username': 'Username used for authentication (email address).',
    'password': 'Password used for authentication.',
    'ac_hostname': 'Hostname of the admin console.',
    'appcfg_flags': 'Extra flags to pass to appcfg.',
    }
# Mandatory options for Config ojects.
REQUIRED_CONFIG_OPTIONS = ['app_id',
                           'cluster_hostname']


# Default number of retries used to fix a broken update with the
# 'rollback' command.
MAX_ROLLBACK_RETRIES = 2
# Error message appcfg gives when a rollback can be used to fix the
# problem. You have to string-interpolate the username (everything
# before the @ in the user's email address).
ROLLBACK_ERR_MESSAGE = (r'.*Another transaction by user %s is already in '
                        'progress for .* That user '
                        'can undo the transaction with .*')

# Name of the app.yaml backup file. The original app.yaml has to be
# modified before an SDK test run and is stored as a backup file.
APP_YAML_BACKUP = 'app.yaml.e2e'
# Name of the backends.yaml backup file. In case an existing
# backends.yaml has to be modified before a test run it is stored as
# this backup file.
BACKENDS_YAML_BACKUP = 'backends.yaml.e2e'

# String value of config.ac_hostname for tests against the SDK.
NO_ADMIN_CONSOLE_ON_SDK = 'ADMIN_CONSOLE_NOT_AVAILABLE_FOR_SDK'

# Time in seconds to wait after the SDK has been started. This is
# necessary because the SDK does need some time to initialize and
# cannot be used for testing right away.
SDK_STARTUP_WAIT = 5

# Applications are not always available right away after an update. We
# therefore wait a few seconds before we continue.
APP_DEPLOY_WAIT = 2

DEFAULT_BACKEND_INSTANCES = 2


class Error(Exception):
    """Base error type."""
    pass


class AppcfgError(Error):
    """Raised when using appcfg ended with an error."""
    pass


class ConfigError(Error):
    """Raised when a Config could not be loaded or usedb."""
    pass


def _check_required_config_attr(config, required_attributes):
    """Check that 'config' has all of the required attributes.

    Args:
      config: A Config instance.
      required_attributes: A list of attribute names.

    Raises:
      ValueError: If any of the required attributes is not present.
    """
    for attr in required_attributes:
        if not getattr(config, attr):
            raise ValueError('"config.%s" has to be set.' % attr)


def is_cluster_appserver(cluster_hostname):
    """Check if the cluster hostname identifies an appserver instance.

    For now, we simply identify a 'cluster_hostname' that starts with
    "localhost" as dev_appserver, everything else as appserver.

    Args:
      cluster_hostname: Name of the cluster an app runs in.

    Returns:
      True, if the cluster identifies an appserver instance, False if it
      identifies an SDK.

    Raises:
      TypeError: If 'cluster_hostname' is not a string.
    """
    if not isinstance(cluster_hostname, basestring):
        raise TypeError('"cluster_hostname" must be a string, not %s' %
                        type(cluster_hostname))
    if not cluster_hostname.startswith('localhost'):
        return True
    else:
        return False


# pylint: disable-msg=R0912,R0902
class Config(object):
    """Common configuration parameters for tests.

    After initialization, Config objects will have the following
    attributes:
    - app_id: The identifier of an application (may include domain prefix).
    - display_app_id: The app ID without prefix.
    - domain: The domain where the application is run.
    - partition: The partition where the app is hosted (for example "s~").
    - backend_id: The identifier of the backend.
    - backend_instances: The number of available backend instances.
    - app_hostname: The hostname of the app (eg "appid.appspot.com").
    - ac_hostname: The hostname of the admin-console (eg "appengine.google.com").
    - sdk_dir: Local directory of the SDK.
    - app_dir: Local directory of the application.
    - username: Username used for authentication (email address).
    - password: Password used for authentication.
    - appcfg_flags: Extra flags to pass to appcfg.

    Not all attributes will have values assigned. For example apps which
    do not run in a custom domain will not have a 'domain' attribute
    value.
    """

    # pylint: disable-msg=R0903,R0913
    def __init__(self, app_id, cluster_hostname,
                 backend_id=None, backend_instances=None,
                 sdk_dir=None, app_dir=None,
                 username=None, password=None,
                 ac_hostname=None, appcfg_flags=None):
        """Initialize configuration.

        The 'app_id' consists of three components: partition, domain, and
        display-app-id: [(partition)~][(domain):](display-app-id). Both,
        partition and domain are optional.

        Common 'cluster_hostname' values are "appspot.com" or the domain
        name your app is running on.

        If you specify 'backend_id', then 'app_hostname' attribute will
        point to this particular backend, not the frontend.

        Args:
          app_id: Application ID to use when referring to the application.
          cluster_hostname: Hostname of the cluster where the app is hosted.
          backend_id: Backend identifier.
          backend_instances: Number of available backend instances.
          sdk_dir: Local directory where the SDK is located.
          app_dir: Local directory where the application is located.
          username: Username used for authentication (email address).
          password: Password used for authentication.
          ac_hostname: Hostname of the admin console.
          appcfg_flags: Extra flags to pass to appcfg (string).

        Raises:
          TypeError: If app_id or cluster_hostname are not strings.
        """
        if not isinstance(app_id, basestring):
            raise TypeError('"app_id" must be a string, not %s' % type(app_id))
        if not isinstance(cluster_hostname, basestring):
            raise TypeError('"cluster_hostname" must be a string, not %s' %
                            type(app_id))
        self.app_id = app_id
        if not backend_id:
            self.backend_id = ''
        else:
            self.backend_id = backend_id
        if not backend_instances:
            self.backend_instances = 0
        else:
            self.backend_instances = backend_instances
        self.partition = ''
        self.domain = ''
        self.display_app_id = app_id
        if self.display_app_id.find('~') >= 0:
            self.partition, self.display_app_id = self.display_app_id.split('~')
        if self.display_app_id.find(':') >= 0:
            self.domain, self.display_app_id = self.display_app_id.split(':')
        self.cluster_hostname = cluster_hostname
        if is_cluster_appserver(cluster_hostname):
            # If a backend is specified, point 'app_hostname' to this
            # backend.
            if not backend_id:
                self.app_hostname = '%s.%s' % (self.display_app_id,
                                               cluster_hostname)
            else:
                self.app_hostname = '%s.%s.%s' % (self.backend_id,
                                                  self.display_app_id,
                                                  cluster_hostname)
            if ac_hostname:
                self.ac_hostname = ac_hostname
            else:
                self.ac_hostname = 'appengine.google.com'
        else:
            # We assume a cluster hostname that does not identify an
            # appserver to be an dev_appserver instance. This means
            # the application hostname is the given clustername and no
            # admin console is available.
            self.app_hostname = cluster_hostname
            self.ac_hostname = NO_ADMIN_CONSOLE_ON_SDK
            # TODO(schuppe): configure 'app_hostname' for backends on the SDK.
        self.sdk_dir = sdk_dir if sdk_dir else ''
        self.app_dir = app_dir if app_dir else ''
        self.username = username if username else ''
        self.password = password if password else ''
        self.appcfg_flags = appcfg_flags if appcfg_flags else ''


def load_config_from_file(file_path, index=0, _open_fct=open):
    """Load a Config options from a configuration file.

    The configuration file must be in a format parsable by ConfigParser
    (see http://docs.python.org/library/configparser.html). A
    configuration section name must start with 'config'. If multiple
    sections are defined, they can be addressed in a lexicographical
    order with 'index'.

    A section must contain all options defined in
    REQUIRED_CONFIG_OPTIONS and may contain additional options defined
    in CONFIG_OPTIONS.

    A typical configuration file could look like this:
    '''
    [config]
    app_id: my-app-id
    cluster_hostname: appspot.com
    sdk_dir: /path/to/sdk
    app_dir: /path/to/app
    username: alice@example.com
    password: secret
    ac_hostname: appspot.com
    appcfg_flags: --runtime=python27 -R
    '''

    Args:
      file_path: Path to configuration file.
      index: The index of the section to load a Config object from.
      _open_fct: Function to open the config file (only used for testing).

    Returns:
      A Config object.

    Raises:
      IndexError: If index is larger than the number of config sections.
      ValueError: If config file could not be read.
    """
    parser = ConfigParser.SafeConfigParser()
    parser.readfp(_open_fct(file_path))
    sections = parser.sections()
    sections.sort()
    if len(sections) < 1:
        raise ConfigError('no "config.." section found in %s' % file_path)
    section_name = sections[index]
    kwargs = {}
    for option in CONFIG_OPTIONS:
        if parser.has_option(section_name, option):
            kwargs[option] = parser.get(section_name, option)
    if 'app_id' not in kwargs:
        raise ValueError('"app_id" is not set in config for "%s".' %
                         section_name)
    args = []
    for option in REQUIRED_CONFIG_OPTIONS:
        if option not in kwargs:
            raise ValueError('"%s" is not set in config for "%s".' %
                             (option, section_name))
        args.append(kwargs.pop(option))
    # pylint: disable-msg=W0142
    return Config(*args, **kwargs)


def run_appcfg_with_auth(config, action, options=None, args=None):
    """Run an appcfg command with the given options, action, and arguments.

    If 'config' has a non-empty 'backend_id' attribute, "appcfg backend"
    will be used instead of "appcfg".

    By default, app ID and server are set as given in config.

    Args:
      config: A Config instance.
      action: The action to be performed.
      options: A list of options to be used.
      args: A list of arguments passed to appcfg, e.g., a directory location.

    Returns:
      An (stdout, stderr) tuple.

    Raises:
      ValueError: If one of the configuration attributes is not set.
    """
    required_attributes = ['app_dir', 'sdk_dir', 'username', 'password']
    _check_required_config_attr(config, required_attributes)
    argv = [os.path.join(config.sdk_dir, 'appcfg.py')]
    argv.append('--no_cookies')
    argv.append('--email=' + config.username)
    argv.append('--passin')
    if config.app_id:
        argv.append('--application=%s' % config.app_id)
    if config.appcfg_flags:
        for flag in config.appcfg_flags.split(' '):
            argv.append(flag)
    if config.ac_hostname:
        argv.append('--server=' + config.ac_hostname)
    if options:
        argv += list(options)
    if not config.backend_id:
        # For appcfg calls to frontends the action is followed by the
        # arguments.
        argv.append(action)
        if args:
            argv.extend(args)
    else:
        # For appcfg calls to backends the action is following the
        # arguments.
        argv.append('backends')
        argv.append(config.app_dir)
        if config.app_dir in args:
            args.remove(config.app_dir)
        argv.append(action)
        if args:
            argv.extend(args)
    p = subprocess.Popen(argv, bufsize=0, stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT)
    stdout, stderr = p.communicate(config.password)
    return (stdout, stderr)


def update_app(config, options=None, rollback_retries=MAX_ROLLBACK_RETRIES):
    """Update an application with appcfg.

    If an update fails because a previous update was not cleanly
    finished, a rollback is tried as specified by 'rollback_retries'.
    If the rollback fails as well, 'AppcfgError' is raised. If appcfg
    gives another error which cannot be handled with a rollback an
    'AppcfgError' is raised as well.

    Args:
      config: A Config instance.
      options: A list of options to be used.
      rollback_retries: The maximum number of retries in case the update fails.

    Returns:
      An (stdout, stderr) tuple.

    Raises:
      ValueError: If one of the configuration attributes is not set.
      AppcfgError: If rollback was unsuccessful.
    """
    required_attributes = ['app_dir', 'username']
    _check_required_config_attr(config, required_attributes)
    if options is None:
        options = []
    short_username = config.username.split('@')[0]
    success = False
    (stdout, stderr) = (None, None)
    err_msg = ROLLBACK_ERR_MESSAGE % short_username
    while rollback_retries > 0 and not success:
        stdout, stderr = run_appcfg_with_auth(config, 'update', options,
                                              args=[config.app_dir])
        if re.match(err_msg, stdout, re.DOTALL):
            if not config.backend_id:
                args = [config.app_dir]
            else:
                args = [config.backend_id]
            stdout, stderr = run_appcfg_with_auth(config, 'rollback', options,
                                                  args=args)
            if 'Error' in stdout:
                raise AppcfgError('Could not rollback: %s' % stdout)
            rollback_retries -= 1
        elif 'Error' in stdout:
            msg = 'Could not update : %s' % stdout
            raise AppcfgError(msg)
        else:
            time.sleep(APP_DEPLOY_WAIT)
            success = True
    return stdout, stderr


class DevAppServerThread(threading.Thread):
    """A thread class that can be used to run dev_appserver.

    '''
    dev_appserver_thread = DevAppServerThread(config)
    dev_appserver_thread.start()
    ...
    dev_appserver_thread.stop()
    '''
    """

    def __init__(self, config, options=None, clear_datastore=True):
        """Initialize thread object.

        By default, the local datastore is cleared.

        Args:
          config: A Config instance.
          options: A list of options to be used.
          clear_datastore: Clear datastore before starting dev_appserver.
        """
        threading.Thread.__init__(self)
        required_attributes = ['app_id', 'app_dir', 'sdk_dir', 'app_hostname']
        _check_required_config_attr(config, required_attributes)
        self.config = config
        if options is None:
            self.options = []
        else:
            self.options = options
        self.clear_datastore = clear_datastore
        self.pid = None
        self.app_yaml_path = os.path.join(self.config.app_dir, 'app.yaml')
        self.app_yaml_bak_path = os.path.join(self.config.app_dir,
                                              APP_YAML_BACKUP)

    def _get_argv(self):
        """Build dev_appserver arguments from __init__ arguments.

        Returns:
          A list of arguments to use when starting dev_appserver.

        Raises:
          ValueError: If app_hostname does not match localhost:PORT.
        """
        argv = []
        if self.config.app_hostname.count(':') > 1:
            raise ValueError('Expected at most 1 colon in ' +
                             'config.app_hostname: "%s"' %
                             self.config.app_hostname)
        app_hostname_parts = self.config.app_hostname.split(':')
        if len(app_hostname_parts) == 1:
            port_option = ''
        else:
            port_option = '--port=%s' % app_hostname_parts[1]
        argv.append(os.path.join(self.config.sdk_dir, 'dev_appserver.py'))
        argv.append('--skip_sdk_update_check')
        argv.append(port_option)
        if self.clear_datastore:
            argv.append('--clear_datastore')
        argv.extend(self.options)
        argv.append(self.config.app_dir)
        return argv

    def _replace_app_yaml(self):
        """Replace the original application's app.yaml with a working copy.


        This is necessary because dev_appserver doesn't provide a
        command-line option for overriding the application id.

        The original app.yaml is saved and can be restored with
        _restore_app_yaml().

        """
        shutil.copy(self.app_yaml_path, self.app_yaml_bak_path)
        f = fileinput.FileInput(self.app_yaml_path, inplace=1)
        for line in f:
            if line.startswith('application:'):
                line = 'application: %s' % self.config.app_id
            else:
                line = line.strip(os.linesep)
            print line
        f.close()

    def _restore_app_yaml(self):
        """Restore the original app.yaml file."""
        os.remove(self.app_yaml_path)
        shutil.copy(self.app_yaml_bak_path, self.app_yaml_path)
        os.remove(self.app_yaml_bak_path)

    def start(self):
        self._replace_app_yaml()
        super(DevAppServerThread, self).start()
        # We need to give dev_appserver some time to start up.
        time.sleep(SDK_STARTUP_WAIT)
        # TODO(schuppe): Add a check whether the dev_appserver is actually
        # running.

    def run(self):
        argv = self._get_argv()
        popen_obj = subprocess.Popen(argv, bufsize=0, stdin=subprocess.PIPE,
                                     stdout=subprocess.PIPE,
                                     stderr=subprocess.PIPE)
        self.pid = popen_obj.pid
        # communicate() will keep reading from stdin and
        # stderr. Without it, the buffer would be filled up and the
        # process blocked until the buffer can accept more data.
        popen_obj.communicate()

    def stop(self):
        if self.pid:
            # We have to kill dev_appserver the hard way. SIGTERM is
            # sometimes ignored which causes tests to stall until they are
            # killed externally.
            os.kill(self.pid, signal.SIGKILL)
        self._restore_app_yaml()


def _create_backends_yaml(config):
    """Create a backends.yaml file from config.

    From the config object, 'backend_id' and 'backend_instances' are
    used to create a valid a backends.yaml file. An existing
    backend.yaml file will be moved to BACKENDS_YAML_BACKUP in the same
    directory.

    Args:
      config: A Config instance.
    """
    backends_yaml_path = os.path.join(config.app_dir, 'backends.yaml')
    backends_yaml_backup_path = os.path.join(config.app_dir,
                                             BACKENDS_YAML_BACKUP)
    if os.path.exists(backends_yaml_path):
        shutil.copy2(backends_yaml_path, backends_yaml_backup_path)
    if config.backend_instances:
        instances = config.backend_instances
    else:
        instances = DEFAULT_BACKEND_INSTANCES
    lines = []
    lines.append('backends:')
    lines.append('- name: %s' % config.backend_id)
    lines.append('  options: public, dynamic')
    lines.append('  instances: %s' % instances)
    backends_yaml = open(backends_yaml_path, 'w')
    backends_yaml.write(os.linesep.join(lines))
    backends_yaml.close()


def _restore_backends_yaml(config):
    """Restore backends.yaml file.

    If a backup of backends.yaml file was created with
    _create_backends_yaml(), this function will restore the original
    content and remove the backup file.

    Args:
      config: A Config instance.
    """
    backends_yaml_path = os.path.join(config.app_dir, 'backends.yaml')
    backends_yaml_backup_path = os.path.join(config.app_dir,
                                             BACKENDS_YAML_BACKUP)
    if os.path.exists(backends_yaml_backup_path):
        shutil.copy2(backends_yaml_backup_path, backends_yaml_path)
        os.remove(backends_yaml_backup_path)


def setup_app(config):
    """Set up an application for testing.

    Depending on 'config', an application will either be uploaded to an
    app_server instance or a local dev_appserver is started to run the
    application.

    If config has 'backend_id' assigned, the given application will be
    uploaded to this backend and the backend will be started.

    It is important that you also invoke teardown_app() when you are done
    testing. This will (a) shutdown dev_appserver, (b) stop a backend,
    or (c) do nothing for normal frontend apps.

    Args:
      config: A Config instance.

    Returns:
      A token that identifies the app. This token has to be passed to
      teardown_app().
    """
    if is_cluster_appserver(config.cluster_hostname):
        if config.backend_id:
            _create_backends_yaml(config)
        stdout, _ = update_app(config)
        # stdout is not a list - pylint: disable-msg=E1103
        assert 'error' not in stdout.lower(), stdout
        if config.backend_id:
            args = [config.backend_id]
            stdout, _ = run_appcfg_with_auth(config, 'start', args=args)
            if not 'is already started' in stdout:
                # stdout is not a list - pylint: disable-msg=E1103
                assert 'error' not in stdout.lower(), stdout
        return None
    else:
        thread = DevAppServerThread(config)
        thread.start()
        return thread


def teardown_app(config, app_token):
    """Tear down application used for testing.

    This is the counterpart to setup_app().

    Args:
      config: A Config instance.
      app_token: A token identifying the application used for testing.
    """
    if is_cluster_appserver(config.cluster_hostname):
        if config.backend_id:
            args = [config.backend_id]
            stdout, _ = run_appcfg_with_auth(config, 'stop', args=args)
            if not 'is already stopped' in stdout:
                # stdout is not a list - pylint: disable-msg=E1103
                assert 'error' not in stdout.lower(), stdout
            stdout, _ = run_appcfg_with_auth(config, 'delete', args=args)
            # stdout is not a list - pylint: disable-msg=E1103
            assert 'error' not in stdout.lower(), stdout
            _restore_backends_yaml(config)
    else:
        app_token.stop()
