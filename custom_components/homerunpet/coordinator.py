"""DataUpdateCoordinator for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
from typing import Any, Dict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import (
    ACCOUNT_TYPE_EMAIL,
    CONF_ACCOUNT_TYPE,
    CONF_AREA_CODE,
    CONF_FAMILY_ID,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_USERNAME,
    DEFAULT_SCAN_INTERVAL_SEC,
    DOMAIN,
)
from .homerun_api import (
    HomerunApiClient,
    HomerunAuthError,
    HomerunConnectionError,
    HomerunError,
)

_LOGGER = logging.getLogger(__name__)


class HomerunDataUpdateCoordinator(DataUpdateCoordinator[Dict[str, Dict[str, Any]]]):
    """Class to manage fetching Homerun data from the cloud API."""

    config_entry: ConfigEntry

    def __init__(
        self,
        hass: HomeAssistant,
        client: HomerunApiClient,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the coordinator."""
        self.client = client
        self.entry = entry
        self.family_id = entry.data.get(CONF_FAMILY_ID)
        self.ez_token_data: Dict[str, Any] = {}

        scan_interval = entry.options.get(
            CONF_SCAN_INTERVAL,
            entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SEC),
        )

        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=f"{DOMAIN}_{entry.entry_id}",
            update_interval=timedelta(seconds=scan_interval),
        )

    async def _async_reauth(self) -> None:
        """Attempt to re-authenticate with stored credentials."""
        account_type = self.entry.data.get(CONF_ACCOUNT_TYPE)
        username = self.entry.data.get(CONF_USERNAME, "")
        password = self.entry.data.get(CONF_PASSWORD, "")
        area_code = self.entry.data.get(CONF_AREA_CODE, "+86")
        region = self.entry.data.get(CONF_REGION, "CN")

        _LOGGER.info("Token expired, attempting re-login for %s", username)
        if account_type == ACCOUNT_TYPE_EMAIL:
            await self.client.async_login_email(username, password, country_code=region)
        else:
            await self.client.async_login_phone(
                username, password, area_code=area_code, country_code=region
            )

    async def _async_update_data(self) -> Dict[str, Dict[str, Any]]:
        """Fetch data from API for all devices."""
        try:
            # If no family_id stored, fetch the current active family
            if not self.family_id:
                families = await self.client.async_get_families()
                if families:
                    current_family = next((f for f in families if f.get("current") == 1), families[0])
                    self.family_id = current_family.get("id")

            if not self.family_id:
                _LOGGER.warning("No families found for Homerunpet account")
                return {}

            # Fetch list of devices in family
            devices_list = await self.client.async_get_devices(int(self.family_id))
            if not devices_list:
                return {}

            # Fetch Ezviz token for camera streaming if not present
            if not self.ez_token_data or not self.ez_token_data.get("accessToken"):
                self.ez_token_data = await self.client.async_get_ez_token()

            # Fetch properties for each device in parallel
            tasks = []
            for dev in devices_list:
                serial = dev.get("deviceSerial")
                if serial:
                    tasks.append(self._fetch_device_info_and_properties(dev))

            results = await asyncio.gather(*tasks, return_exceptions=True)

            data: Dict[str, Dict[str, Any]] = {}
            for res in results:
                if isinstance(res, Exception):
                    _LOGGER.warning("Error fetching device data: %s", res)
                    continue
                if res and "serial" in res:
                    data[res["serial"]] = res

            return data

        except HomerunAuthError as err:
            try:
                await self._async_reauth()
                # Retry once after reauth
                return await self._async_update_data()
            except Exception as auth_err:
                raise ConfigEntryAuthFailed(
                    f"Authentication failed: {auth_err}"
                ) from err
        except HomerunConnectionError as err:
            raise UpdateFailed(f"Connection error: {err}") from err
        except HomerunError as err:
            raise UpdateFailed(f"API error: {err}") from err
        except Exception as err:
            raise UpdateFailed(f"Unexpected error: {err}") from err

    async def _fetch_device_info_and_properties(
        self, dev_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch properties for a single device and format output."""
        serial = dev_info.get("deviceSerial")
        if not serial:
            return {}

        properties, details = await asyncio.gather(
            self.client.async_get_device_properties(serial),
            self.client.async_get_device_info(serial),
        )

        # The list API identifies the parent appliance, while the detail API
        # carries cameraList with the Ezviz child serial used by the official app.
        merged_device = dict(dev_info)
        if details:
            merged_device.update(details)

        # Merge device properties with any status in dev_info
        return {
            "serial": serial,
            "device": merged_device,
            "properties": properties or {},
        }
