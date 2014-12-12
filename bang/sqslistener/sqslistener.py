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

import os
import yaml
import logging
import logging.config
import time
import boto.sqs
import response_states
from sqsjobs import SQSJobs
from boto.sqs.message import Message
from boto.exception import SQSError
from non_daemonized_pool import MyPool
from sqsmultiprocessutils import start_job_process
from request_message import RequestMessage
from request_message import RequestMessageException
from response_message import ResponseMessage
from sqsjobs import SQSJobError

DEFAULT_POOL_PROCESSES = 5
DEFAULT_CONFIG_LEVEL = logging.INFO

class SQSListenerException(Exception):
    pass

class MissingQueueException(Exception):
    pass


class SQSListener:

    def __init__(self,
                 aws_region=None,               # eg. "us-east-1"
                 queue_name=None,               # eg. "bang-queue",
                 response_queue_name=None,      # eg. "bang-response",
                 polling_interval=None,         # eg. 2 # in seconds
                 jobs_config_path=None,         # eg. /home/user/sqslistener/sqs-jobs.yml
                 logging_config_path=None,      # eg. /home/user/sqslistener/logging-config.yml
                 listener_config_path=None):    # eg. /home/user/.sqslistener

        ### Load Sqslistener Configuration ###
        listener_config_yaml = self.load_sqs_listener_config(listener_config_path)

        ### Set up logging ###
        if logging_config_path is None:
            logging_config_path = listener_config_yaml['logging_config_path']

        self.logger = self.setup_logging(logging_config_path)
        self.logger.info("Starting up SQS Listener...")

        ### Set up the remainder of the listener configuration ###
        if jobs_config_path is None:
            self.logger.info("Getting jobs config path from listener config...")
            jobs_config_path = listener_config_yaml['jobs_config_path']
        if aws_region is None:
            self.logger.info("Getting aws region from listener config...")
            aws_region = listener_config_yaml['aws_region']
        if queue_name is None:
            self.logger.info("Getting job queue name config path from listener config...")
            queue_name = listener_config_yaml['job_queue_name']
        if response_queue_name is None:
            self.logger.info("Getting response queue name from listener config...")
            response_queue_name = listener_config_yaml['response_queue_name']
        if polling_interval is None:
            self.logger.info("Getting polling interval length from listener config...")
            polling_interval = listener_config_yaml['polling_interval']

        ### Connect to AWS ###
        self.conn = self.connect_to_sqs(aws_region)
        self.logger.info("Connecting to request queue: %s" % queue_name)
        self.queue = self.conn.get_queue(queue_name)
        self.logger.info("Connecting to response queue: %s" % response_queue_name)
        self.response_queue = self.conn.get_queue(response_queue_name)

        if self.queue is None:
            error_msg = "Queue %s does not exist." % queue_name
            self.logger.critical(error_msg)
            raise MissingQueueException(error_msg)
        if self.response_queue is None:
            error_msg = "Queue %s does not exist." % response_queue_name
            self.logger.critical(error_msg)
            raise MissingQueueException(error_msg)

        ### Import Jobs definition ###
        self.logger.info("Importing jobs definition from: %s ..." % jobs_config_path)
        self.job_set = SQSJobs()
        self.job_set.load_jobs_from_file(jobs_config_path)

        ### Set up polling ###
        self.logger.info("Setting up polling...")
        self.polling_interval = polling_interval
        self.pool = MyPool(processes=DEFAULT_POOL_PROCESSES)

        self.polling = False
        self.logger.info("Set up complete.")


    def load_sqs_listener_config(self, listener_config_path=None):
        if listener_config_path is None or listener_config_path == "":
            listener_config_path = os.path.join(os.environ['HOME'], '.sqslistener')
        try:
            with open(listener_config_path) as f:
                ret = yaml.safe_load(f)
                return ret
        except Exception, e:
            raise SQSListenerException("Problem loading listener config file, %s: %s " % (listener_config_path, str(e)))

    def setup_logging(self, logging_config_path):
        if os.path.exists(logging_config_path):
            with open(logging_config_path, 'rt') as f:
                config = yaml.safe_load(f.read())

            logging.config.dictConfig(config)
        else:
            logging.basicConfig(level=DEFAULT_CONFIG_LEVEL)

        return logging.getLogger("SQSListener")

    def connect_to_sqs(self, aws_region):
        self.logger.info("Connecting to SQS...")
        self.logger.info("Connecting to Region: %s" % aws_region)
        return boto.sqs.connect_to_region(aws_region)

    def post_response(self, response):
        """Post a response to the response queue."""
        message = Message()
        message.set_body(response)

        self.logger.info("Posting response:\n%s" % str(response))
        self.response_queue.write(message)

    def poll_queue(self):
        try:
            polling_response = self.queue.get_messages()

            for message in polling_response:
                self.process_message(message)

        except SQSError:
            self.logger.ERROR("An error occurred polling a queue.")

    def process_message(self, message):
        if type(message) is not Message:
            raise Exception("Message could not be read.")
        try:
            request_message = RequestMessage(message)
            self.logger.info("Processing message %s for job %s" % (request_message.request_id, request_message.job_name))
            job = self.job_set.generate_job(request_message.job_name, request_message.job_parameters)

            started_response_message = ResponseMessage(job_name=request_message.job_name,
                                                       request_id=request_message.request_id,
                                                       job_state="started",
                                                       additional_message="Request has been received and the job is in progress.")

            started_response_message_body = started_response_message.dump_yaml()
            self.post_response(started_response_message_body)

            completed_message_body = start_job_process(self.pool,
                                                       job, request_message.request_id,
                                                       self.response_queue,
                                                       request_message)
            request_id = request_message.request_id
            self.logger.info("Sending message to response queue: %s" % request_id)
            self.post_response(completed_message_body)
        except RequestMessageException, e:
            self.logger.exception(e)
            job_missing_response_message = ResponseMessage(job_name="unknown",
                                                           request_id="unknown",
                                                           job_state=response_states.failure,
                                                           additional_message="Invalid Message: %s" % str(e))
            response_body = job_missing_response_message.dump_yaml()
            self.post_response(response_body)
        except SQSJobError, e:
            self.logger.error("An error occurred with the job: %s", str(e))
            job_missing_response_message = ResponseMessage(job_name=request_message.job_name,
                                                           request_id=request_message.request_id,
                                                           job_state=response_states.failure,
                                                           additional_message="Job definition is missing.")
            response_body = job_missing_response_message.dump_yaml()
            self.post_response(response_body)
        except Exception, e:
            self.logger.error("An error occurred processing a message: %s", str(e))

            if type(message) is boto.sqs.message.Message:
                msg = message.get_body()
            else:
                msg = str(message)

            job_missing_response_message = ResponseMessage(job_name='unknown',
                                                           request_id='unknown',
                                                           job_state=response_states.failure,
                                                           additional_message="There was a problem with your request Message, %s:\n%s"% (str(e), msg))
            response_body = job_missing_response_message.dump_yaml()
            self.post_response(response_body)
        finally:
            self.queue.delete_message(message)

    def start_polling(self):
        self.logger.info("Starting polling...")
        self.polling = True

        while self.polling:
            self.poll_queue()
            time.sleep(self.polling_interval)

        self.logger.info("Polling stopped.")
