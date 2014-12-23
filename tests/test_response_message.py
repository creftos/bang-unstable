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

import unittest
import yaml

from bang.sqslistener.response_message import ResponseMessage


class TestResponseMessage(unittest.TestCase):

    def yaml_dump_test(self):
        job_name = "testjob1"
        request_id = "226a4190-38c9-4490-9bdf-ea96e538787f"
        job_state = "started"
        additional_message = "one\ntwo\nthree"

        test_response_message = ResponseMessage(job_name, request_id, job_state, additional_message)

        dumped_yaml = test_response_message.dump_yaml()

        loaded_yaml = yaml.load(dumped_yaml)

        print loaded_yaml['result']

        assert loaded_yaml['name'] == job_name
        assert loaded_yaml['request_id'] == request_id
        assert loaded_yaml['message'] == additional_message
        assert loaded_yaml['result'] == job_state

