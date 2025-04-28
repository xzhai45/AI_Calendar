# home/signals.py
from allauth.socialaccount.signals import social_account_added
from allauth.socialaccount.models import SocialToken
from django.dispatch import receiver
import logging

logger = logging.getLogger(__name__)

@receiver(social_account_added)
def fetch_and_log_token(sender, request, sociallogin, **kwargs):
    account = sociallogin.account
    logger.debug(f"social_account_added triggered for account: {account}")
    
    try:
        token = SocialToken.objects.get(account=account)
        logger.debug(f" Token found: {token.token}")
    except SocialToken.DoesNotExist:
        logger.error(f" No token found for account: {account}")
