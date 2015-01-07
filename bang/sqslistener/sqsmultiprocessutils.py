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


from bang.config import Config
from bang.stack import Stack
from response_message import ResponseMessage
from sqslistener_callbacks import SQSListenerPlaybookCallbacks, SQSListenerPlaybookRunnerCallbacks
import ansible
import response_states
import listener_utils

import logging
import multiprocessing
from multiprocessing import Process
logger = logging.getLogger("SQSListener")

### Monkey patch to grab logged output from paramiko for sqslister logs instead. ###
def monkey_patched_verbose(msg, host=None, caplevel=2):
    """ Overrides output given by paramiko.
        Rationale: This seemed a lot better than copying and pasting the whole library and fixing the output
                   wherever I found it.
    """
    logger.info("%s - %s" % (host, msg))
    # TODO: Find a way to send a message with this information as well.
    # TODO: Add multiprocessing logging for s3bucket logs.

ansible.callbacks.verbose = monkey_patched_verbose
# logger.debug("Note that ansible.callbacks.verbose has been monkey patched!")
### End monkey patch ###

def start_job_process(pool, job, request_id, message_queue, request_message, request_logger_name=None):
    if request_logger_name:
        _mlog = multiprocessing.get_logger()
        request_logger = _mlog.manager.getLogger(request_logger_name)

    if job:
        result = pool.apply_async(perform_job, [job, request_id, message_queue, request_message, request_logger_name])
        return result.get()
    else:
        log_msg = "Job with request_id %s, does not exist." % str(request_id)
        logger.error(log_msg)
        if request_logger:
            request_logger(log_msg)


def perform_job(job, request_id, message_queue, request_message, request_logger_name):
    if request_logger_name:
        _mlog = multiprocessing.get_logger()
        request_logger = _mlog.manager.getLogger(request_logger_name)
    else:
        request_logger = None

    try:
        config = Config.from_config_specs(job.bang_stacks)
        stack = Stack(config)
        stack.deploy()

        stack.configure(playbook_callbacks_class=SQSListenerPlaybookCallbacks,
                        playbook_runner_callbacks_class=SQSListenerPlaybookRunnerCallbacks,
                        sqs_response_queue=message_queue,
                        request_message=request_message,
                        request_logger_name=request_logger_name)

    except Exception as e:  # Catch exception to send as response message.
        logger.exception(e)

        if request_logger:
            request_logger.exception(e)

        yaml_response = ResponseMessage(job.name, request_id, response_states.failure,
                                        "%s. See sqslistener logs for a complete stack trace." % str(e))
        return yaml_response.dump_yaml()

    yaml_response = ResponseMessage(job.name, request_id, response_states.success)
    return yaml_response.dump_yaml()