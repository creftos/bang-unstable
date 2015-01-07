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

import logging
import multiprocessing
import datetime as D
from logging import Logger as log


_mlog = multiprocessing.get_logger()

DATETIME_FILENAME_FORMAT = "%Y-%m-%d:%H:%M:%S"


def get_logger_name(job_name, request_id):
    return '%s-%s' % (job_name, request_id)

def get_log_filename(logger_name):
    return "%s-%s.log" % (D.datetime.now().strftime(DATETIME_FILENAME_FORMAT), logger_name)
