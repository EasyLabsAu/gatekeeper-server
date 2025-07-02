import logging

import requests
from requests.exceptions import ConnectionError as RequestsConnectionError
from requests.exceptions import HTTPError, RequestException, Timeout
from tenacity import (
    after_log,
    before_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from core.config import settings
from helpers.logger import Logger

logger = Logger(__name__)


class Notifier:
    def __init__(self, url, headers=None, timeout=10, max_retries=5):
        self.url = url
        self.headers = headers or {"Content-Type": "application/json"}
        self.timeout = timeout
        self.max_retries = max_retries

    @retry(
        reraise=True,
        stop=stop_after_attempt(5),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(
            (RequestException, Timeout, RequestsConnectionError)
        ),
        before=before_log(logger, logging.INFO),
        after=after_log(logger, logging.INFO),
    )
    def send(self, data):
        try:
            logger.info("Sending POST request to %s", self.url)
            response = requests.post(
                self.url, json=data, headers=self.headers, timeout=self.timeout
            )
            response.raise_for_status()  # Raise an HTTPError on bad HTTP status
            logger.info("Request succeeded")
            return response.json()  # Or response.text, based on your needs
        except HTTPError as e:
            logger.error("HTTP error occurred: %s", e)

        except Timeout as e:
            logger.error("Request timed out: %s", e)

        except RequestsConnectionError as e:
            logger.error("Connection error occurred: %s", e)

        except ValueError as e:
            logger.error("Invalid JSON response: %s", e)

        except RequestException as e:
            logger.error("Request failed: %s", e)


error_notifier = Notifier(settings.SLACK_ERROR_WEBHOOK)
info_notifier = Notifier(settings.SLACK_INFO_WEBHOOK)
