from .jwt import get_user_from_access_token
import logging

logger = logging.getLogger(__name__)

def authenticate(token):
    user = get_user_from_access_token(token)
    logger.debug("isStaff: %s, isActive: %s",user.is_staff,user.is_active )
    if user.is_staff and user.is_active:
        return True

    return False