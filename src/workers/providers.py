from src.helpers.logger import Logger
from src.models.providers import ProviderManage, ProviderManageAction
from src.repositories.providers import ProviderRepository

logger = Logger(__name__)


async def on_provider_created(email: str):
    provider_repository: ProviderRepository = ProviderRepository()
    await provider_repository.manage(
        ProviderManageAction.START_EMAIL_VERIFICATION, ProviderManage(email=email)
    )
