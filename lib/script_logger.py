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

import os
import sys
import getpass
import inspect
import datetime
import logging


class Logger(logging.Logger):

    def __init__(self, name=False, console=False, level='INFO'):
        """
        Setup Logging for panAF
        :param str name: Filename. Default is picked up by the running script name.
        :param bool console: Print to console
        :param level: Logging level. Default: "INFO"
        """
        self.absolute_location = os.path.abspath(os.path.dirname(__file__))
        if '/' not in inspect.stack()[1]:
            self.directory = os.getcwd()
        else:
            self.directory = self.absolute_location.rsplit('/', 1)[0]
        self.filename = inspect.stack()[1].filename
        self.time = datetime.datetime.now()
        self.user = getpass.getuser()
        self.pid = os.getpid()

        if not name:
            name = self.filename

        log_filename = self.time.strftime("%Y-%m-%d-%H:%M:%S") + "-" + str(self.pid) + ".log"
        log_directory = self.directory + "/logs/"
        if not os.path.exists(log_directory):
            os.makedirs(log_directory)

        self._level = getattr(logging, level.upper(), logging.INFO)
        self.log = logging.getLogger(self.filename)

        file_handler = logging.FileHandler(os.path.join(log_directory, log_filename))
        formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] '
                                      '%(message)s', '%Y-%m-%d %H:%M:%S')
        file_handler.setFormatter(formatter)
        super(Logger, self).__init__(name)
        super(Logger, self).addHandler(file_handler)
        super(Logger, self).setLevel(self._level)
        if console:
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            super(Logger, self).addHandler(console_handler)
        self.log_directory = log_directory
        self.log_filename = log_filename

    def get_log_location(self):
        """
        Return log location
        :return: Log location in string format.
        """
        return self.log_directory + self.log_filename