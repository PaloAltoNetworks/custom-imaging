# Copyright 2019 Palo Alto Networks
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sys
import re
from select import select
import time

import yaml
import paramiko


RESTART = 660
RETRY = 120


class PanosDevice(object):
    def __init__(self, logger, **kwargs):
        self._kwargs = kwargs
        self.host = kwargs.get('host')
        self.connected = 0
        self.logger = logger
        try:
            logger.info(f'*** Connecting to device {self.host} ***')
            self.handle = Handle(logger,
                                 host=self.host,
                                 user=kwargs['user'],
                                 ssh_key_file=kwargs['ssh_key_file'])
        except ConnectionError:
            raise Exception("Cannot connect to Device %s" % self.host)
        self.connected = 1
        self.logger.info("*** Connection successful ***")
        self.prompt = "> "
        self._setup()

    def _setup(self):
        self.exec(command='set cli scripting-mode on')
        self.exec(command='set cli confirmation-prompt off')
        self.exec(command='set cli terminal width 500')
        output = self.exec(command='set cli terminal height 500')
        self.prompt = output.response().rsplit(' ')[0]

    def execute(self, **kwargs):
        if 'pattern' in kwargs.keys():
            pattern = kwargs.pop('pattern')
        else:
            pattern = self.prompt
        kwargs['pattern'] = pattern
        if 'command' not in kwargs:
            raise Exception('"command" is mandatory for PanosDevice.execute()')
        kwargs['device'] = self
        kwargs['cmd'] = kwargs.pop('command')
        return self.handle.execute_command(**kwargs)

    def exec(self, *args, **kwargs):
        if not kwargs and not args:
            raise Exception('Command for device is not specified')
        if not kwargs and args[0]:
            kwargs['command'] = args[0]
            if len(args) > 1 and args[1]:
                kwargs['timeout'] = args[1]

        if 'command' not in kwargs:
            raise Exception('Command for device not specified')
        try:
            patt_match = self.execute(**kwargs)
            if patt_match == -1:
                raise Exception('Timeout seen while retrieving output')
            else:
                return Output(response=self.response, status=True)
        except TimeoutError:
            raise Exception("Timeout seen while retrieving output")

    def restart_system(self):
        try:
            self.exec(command='request restart system', pattern=['NOW!', 'Broadcast message from root'])
        except Exception as e:
            if 'Timeout seen while retrieving output' in str(e):
                self.logger.info('Device is now rebooting.')
                self.close()
            else:
                raise Exception('Failed to reboot device.')
        self.logger.info("Waiting for the device to restart...")
        time.sleep(RESTART)
        try:
            self.__init__(self.logger, **self._kwargs)
        except:
            self.logger.error('Unable to connect via ssh. Waiting for 2 minutes before retrying.')
            time.sleep(RETRY)
            self.__init__(self.logger, **self._kwargs)

    def license(self, auth_code):
        if auth_code != '':
            self.logger.info('*** Licensing VM-Series ***')
            self.exec(f'request license fetch auth-code {auth_code}').response()
            time.sleep(5)
            self.logger.info('*** Waiting for VM-Series to boot up with the new license ***')
            self.restart_system()
            self.logger.info('*** Licensing is Complete ***')
            time.sleep(10)
        else:
            self.logger.info('*** No Auth-code provided. Licensing skipped ***')

    def delicense(self, api_key):
        if api_key != '':
            self.logger.info('*** Delicensing VM-Series ***')
            self.exec(f'request license api-key set key {api_key}')
            self.exec(f'request license deactivate VM-Capacity mode auto')
        else:
            self.logger.info('*** No API Key provided. De-licensing skipped ***')
        return

    def private_data_reset(self):
        try:
            self.exec(command='request system private-data-reset', pattern=['NOW!', 'Broadcast message from root'])
        except Exception as e:
            if 'Timeout seen while retrieving output' in str(e):
                self.logger.info('Device is now rebooting.')
                self.close()
            else:
                raise Exception('Failed to reboot device.')
        self.logger.info("Waiting for the device to restart...")
        time.sleep(RESTART)
        try:
            self.__init__(self.logger, **self._kwargs)
        except:
            self.logger.info('Unable to connect via ssh. Waiting for 2 minutes before retrying.')
            time.sleep(RETRY)
            self.__init__(self.logger, **self._kwargs)

    def config(self, **kwargs):
        exec_prompt = self.prompt
        self.prompt = self.prompt[:-1] + "#"
        if 'command' not in kwargs:
            raise Exception('Command for device not specified')
        if 'commit' not in kwargs:
            kwargs['commit'] = True
        get_prompt = self.execute(command='configure')
        if get_prompt == -1:
            raise Exception('Unable to switch to configure mode')
        if isinstance(kwargs['command'], str):
            kwargs['command'] = [kwargs['command']]
        for config_cmd in kwargs['command']:
            get_prompt = self.execute(command=config_cmd)
            if get_prompt == -1:
                raise Exception('Unable to execute command in configure mode.')
        if kwargs['commit']:
            get_prompt = self.execute(command='commit')
            if get_prompt == -1 or 'Configuration committed successfully' not in self.response:
                raise Exception('Unable to execute command in configure mode. ERROR: ' + self.response)
        self.prompt = exec_prompt
        get_prompt = self.execute(command='exit')
        if get_prompt == -1:
            raise Exception('Unable to switch to op mode')

    def verify_system(self):
        try:
            output = yaml.safe_load(self.exec('show system info').response())
        except:
            raise Exception('Unable to fetch system info.')
        if output['vm-license'] == 'none':
            raise Exception('VM-Series Instance is not licensed.')
        if output['serial'] == 'unknown':
            raise Exception('VM-Series Instance does not have a serial.')
        self.logger.info('*** System Check Passed ***')
        return True

    def verify_versions(self, sw, plugin):
        try:
            output = yaml.safe_load(self.exec('show system info').response())
        except:
            raise Exception('Unable to fetch system info.')
        if sw not in output['sw-version']:
            raise Exception(f'Upgraded PanOS version {sw} is not installed properly.')
        if plugin:
            if plugin not in output['vm_series']:
                raise Exception(f'Plugin version {plugin} is not installed properly.')
        self.logger.info('*** Version Check Passed ***')
        return True

    def check_job(self, job_id):
        output = self.exec(f'show jobs id {job_id}').response()
        if 'not found' in output:
            raise Exception(f'Job with job id {job_id} not created.')
        time.sleep(10)
        retry = 25
        interval = 30
        while retry >= 0:
            output = self.exec(f'show jobs id {job_id}').response()
            if 'FIN' in output:
                self.logger.info(f'*** Job {job_id} complete. ***')
                time.sleep(10)
                return True
            elif 'PEND' in output:
                self.logger.info(f'Job {job_id} is incomplete. Waiting for {str(interval)} seconds before retrying.')
                time.sleep(interval)
            else:
                break
        raise Exception(f'Unable to complete job with job id {job_id}')

    def close(self):
        try:
            self.handle.client.close()
            self.connected = 0
        except ConnectionAbortedError:
            raise Exception("Unable to close Device handle")
        return True


class Handle(paramiko.client.SSHClient):
    def __init__(self, logger, **kwargs):
        self.logger = logger
        host = kwargs.get('host')
        user = kwargs.get('user')
        ssh_key_file = kwargs.get('ssh_key_file')
        try:
            super(Handle, self).__init__()
            self.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            self.connect(hostname=host, username=user, key_filename=ssh_key_file)
            ssh_h = self.invoke_shell(width=160)
            self.client = ssh_h
            all_data = []
            while True:
                read, write, error = select([ssh_h], [], [], 10)
                if read:
                    data = ssh_h.recv(32767)
                    try:
                        data = data.decode('utf-8')
                    except UnicodeDecodeError:
                        data = data.decode('iso-8859-1')
                    all_data.append(data)
                    if re.search(r'{0}\s?$'.format(r'(\$|>|#|%)'), data):
                        break
        except Exception as error:
            raise Exception("Cannot create a SSH connection to Device %s: %s: username=%s" % (host, error, user))

    def execute_command(self, **kwargs):
        cmd = kwargs.get('cmd')
        pattern = kwargs.get('pattern')
        device = kwargs['device']
        timeout = kwargs.get('timeout', 300)
        if timeout < 100:
            timeout = 100
        raw_output = kwargs.get('raw_output', False)
        if isinstance(pattern, str):
            pattern = [pattern]
        pattern_new = ''
        for pat in pattern:
            pattern_new = pattern_new + pat + ","
        pattern_new = pattern_new[:-1]
        ssh_h = self.client
        cmd_send = cmd + '\n'
        if not hasattr(device, 'shelltype'):
            device.shelltype = 'sh'
        cmd_cleanup = cmd + '\s?\r{1,2}\n'
        cmd_cleanup = re.sub('\$', '\\$', cmd_cleanup)
        cmd_cleanup = re.sub('\|', '\\|', cmd_cleanup)
        cmd_cleanup = re.sub('-', '\-', cmd_cleanup)
        self.logger.info("Command: " + cmd_send)
        ssh_h.send(cmd_send)
        found = -1
        if 'no_response' in kwargs and kwargs['no_response']:
            device.response = ''
            found = 1
        else:
            (output, resp) = self.expect_output(expected=pattern,
                                                shell=device.shelltype,
                                                timeout=timeout)
            response = ''
            while '--(more)--' in resp:
                response += re.sub('\n--\(more\)--', '', resp, 1)
                ssh_h.send('\r\n')
                (output, resp) = self.expect_output(expected=pattern,
                                                    shell=device.shelltype,
                                                    timeout=timeout)
            response += resp
            if not raw_output:
                response = re.sub(cmd_cleanup, '', response)
            if not output:
                self.logger.info("Sent '%s' to %s, expected '%s', "
                                 "but received:\n'%s'" % (cmd, device.host,
                                                          pattern_new,
                                                          response))
                found = -1
            else:
                for pat in pattern:
                    found += 1
                    if re.search(pat, response):
                        break
            if not raw_output:
                for pat in pattern:
                    response = re.sub('\n.*' + pat, '', response)
                response = re.sub('\r\n$', '', response)
            device.response = response
            self.logger.info("Output: \n" + response + "\n")
        return found

    def expect_output(self, expected='\s\$', timeout=60, shell='sh'):
        time.sleep(0.5)
        timeout -= 2
        ssh_h = self.client
        interval = 10
        time_out = 0
        all_data = ''
        timeout_count = 0
        if isinstance(expected, list):
            if shell == 'csh':
                for i, j in enumerate(expected):
                    expected[i] = re.sub('\s$', '(\s|\t)', expected[i])
            expected = '|'.join(expected)
        while True:
            start_time = time.time()
            read, write, error = select([ssh_h], [], [], interval)
            if read:
                data = ssh_h.recv(4096)
                try:
                    data = data.decode('utf-8')
                except UnicodeDecodeError:
                    data = data.decode('iso-8859-1')
                all_data += data
            end_time = time.time()
            sys.stdout.flush()
            if re.search(r'{0}\s?$'.format(expected), all_data):
                break
            time_out += (end_time - start_time)
            if int(time_out) > timeout:
                timeout_count = 1
                break
        if timeout_count:
            return False, all_data
        return True, all_data


class Output(object):
    def __init__(self, **kwargs):
        self.resp = kwargs.get('response')
        self.stat = kwargs.get('status')

    def response(self):
        return self.resp

    def status(self):
        return self.stat

    def job_id(self):
        return self.resp.split('\n')[-2].replace('\r', '')

    def __bool__(self):
        return self.stat

    def __nonzero__(self):
        return self.__bool__()
