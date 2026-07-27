import asyncio
from typing import Any

from camoufox.async_api import AsyncCamoufox

from .settings import CONFIG


class ManagedSession:
    """Context wrapper over a Camoufox browser with different flags/init."""

    def __init__(self, show_window: bool | None = None):
        self._visible = CONFIG.show_gui if show_window is None else show_window
        self._actor: AsyncCamoufox | None = None

    async def __aenter__(self) -> AsyncCamoufox:
        self._actor = await AsyncCamoufox(
            headless=not self._visible,
            disable_coop=True,
            i_know_what_im_doing=True,
            humanize=False,
            os="windows",
            config={"forceScopeAccess": True},
        ).__aenter__()
        return self._actor

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: Any,
    ) -> None:
        if self._actor:
            await self._actor.__aexit__(exc_type, exc_val, exc_tb)
