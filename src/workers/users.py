from helpers.logger import Logger
from models.users import UserManage, UserManageAction
from services.users import UserService

logger = Logger(__name__)


async def on_user_created(email: str):
    user_service: UserService = UserService()
    await user_service.manage(
        UserManageAction.START_EMAIL_VERIFICATION, UserManage(email=email)
    )
