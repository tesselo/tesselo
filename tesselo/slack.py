import structlog
from django.conf import settings
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

logger = structlog.get_logger("django_structlog")


class SlackClient(WebClient):
    def __init__(self, **kwargs):
        super().__init__(token=settings.SLACK_TOKEN, **kwargs)

    def send_message(self, channel, message):
        try:
            return self.chat_postMessage(channel=channel, text=message)
        except SlackApiError as e:
            logger.error("Failed to send a message to slack", error=e)

    def send_error(self, message):
        return self.send_message(settings.SLACK_ERRORS_CHANNEL, message)

    def send_to_dev_null(self, message):
        return self.send_message(settings.SLACK_DEVNULL_CHANNEL, message)

    def send_to_techies(self, message):
        return self.send_message(settings.SLACK_TECH_CHANNEL, message)
