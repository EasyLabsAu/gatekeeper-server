from helpers.logger import Logger
from models.providers import ProviderManage, ProviderManageAction
from services.providers import ProviderService

logger = Logger(__name__)


async def on_provider_created(email: str):
    provider_service: ProviderService = ProviderService()
    await provider_service.manage(
        ProviderManageAction.START_EMAIL_VERIFICATION, ProviderManage(email=email)
    )
