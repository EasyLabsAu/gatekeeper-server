from src.models.providers import ProviderManage, ProviderManageAction
from src.repositories.providers import ProviderRepository


async def on_provider_created(email: str):
    repository = ProviderRepository()
    await repository.manage(
        ProviderManageAction.START_EMAIL_VERIFICATION, ProviderManage(email=email)
    )
