#!/usr/bin/python
# Copyright 2014 - Brian J. Donohoe
#
# This file is part of bang.
#
# bang is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# bang is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with bang.  If not, see <http://www.gnu.org/licenses/>.

import listener_utils
import time
import logging
import multiprocessing
from bang.util import S3Handler
from logutils.queue import QueueHandler
from logutils.queue import QueueListener
from multiprocessing import Process
import non_daemonized_pool

class S3Logger(object):

    def __init__(self, job_name, request_id, bucket_name):
        _mlog = multiprocessing.get_logger()
        self.logger_name = '.'.join((_mlog.name, listener_utils.get_logger_name(job_name, request_id)))
        self.logger = _mlog.manager.getLogger(self.logger_name)
        self.logger.setLevel(level=logging.INFO)
        self.handler = S3Handler(bucket=bucket_name)
        self.queue = multiprocessing.Queue()
        self.ql = QueueListener(self.queue, self.handler)
        self.ql.start()
        self.qh = QueueHandler(self.queue)
        self.logger.addHandler(self.qh)
        self.logger.addHandler(self.handler)