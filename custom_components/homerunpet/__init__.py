"""The Homerunpet (霍曼宠物) Home Assistant integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_REGION,
    CONF_TOKEN,
    CONF_USER_ID,
    DEFAULT_REGION,
    DOMAIN,
    PLATFORMS,
)
from .coordinator import HomerunDataUpdateCoordinator
from .homerun_api import HomerunApiClient, load_cached_thing_models
from .services import async_setup_services, async_unload_services

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Homerunpet from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    await hass.async_add_executor_job(load_cached_thing_models)

    session = async_get_clientsession(hass)
    region = entry.data.get(CONF_REGION, DEFAULT_REGION)
    token = entry.data.get(CONF_TOKEN)
    user_id = entry.data.get(CONF_USER_ID)

    client = HomerunApiClient(
        session=session,
        region=region,
        token=token,
        user_id=user_id,
    )

    coordinator = HomerunDataUpdateCoordinator(hass, client, entry)
    await coordinator.async_config_entry_first_refresh()

    hass.data[DOMAIN][entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    async_setup_services(hass)

    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
        async_unload_services(hass)

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
