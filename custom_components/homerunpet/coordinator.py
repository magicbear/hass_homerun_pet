"""DataUpdateCoordinator for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

import asyncio
from datetime import timedelta
import logging
import time
from typing import Any, Dict, List, Optional

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
    DEVICES_LIST_TTL_SEC,
    DEFAULT_SCAN_INTERVAL_SEC,
    DOMAIN,
)
from .homerun_api import (
    HomerunApiClient,
    HomerunApiError,
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
        self._devices_cache: Optional[List[Dict[str, Any]]] = None
        self._devices_fetched_at: float = 0.0
        self._device_details: Dict[str, Dict[str, Any]] = {}

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

            # The family device list only changes when devices are paired or
            # removed, so keep it cached and re-fetch at most once per TTL.
            now = time.monotonic()
            if (
                self._devices_cache is None
                or (now - self._devices_fetched_at) > DEVICES_LIST_TTL_SEC
            ):
                devices_list = await self.client.async_get_devices(int(self.family_id))
                self._devices_fetched_at = now
                self._device_details.clear()
                if devices_list:
                    self._devices_cache = devices_list

            devices_list = self._devices_cache or []
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

    async def async_refresh_devices(self) -> None:
        """Invalidate the cached device list and refresh all data."""
        self._devices_cache = None
        self._device_details.clear()
        await self.async_request_refresh()

    async def _fetch_device_info_and_properties(
        self, dev_info: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Fetch properties for a single device and format output."""
        serial = dev_info.get("deviceSerial")
        if not serial:
            return {}

        # Full device details (cameraList etc.) change as rarely as the device
        # list itself, so only fetch them once per device-list refresh.
        details = self._device_details.get(serial)
        if details is None:
            details = await self.client.async_get_device_info(serial)
            if details:
                self._device_details[serial] = details

        properties, exceptions = await asyncio.gather(
            self.client.async_get_device_properties(serial),
            self.client.async_get_device_exceptions(serial),
        )

        # Keep the server-provided, localized warning text. This is the same
        # list rendered by the official app's exception dialog.
        properties = dict(properties or {})
        properties["exception_messages"] = exceptions

        # The list API identifies the parent appliance, while the detail API
        # carries cameraList with the Ezviz child serial used by the official app.
        merged_device = dict(dev_info)
        if details:
            merged_device.update(details)

        # Merge device properties with any status in dev_info
        return {
            "serial": serial,
            "device": merged_device,
            "properties": properties,
        }

    async def async_set_device_properties(
        self, device_serial: str, properties: Dict[str, Any]
    ) -> bool:
        """Send property updates to device with automatic re-auth on token expiration."""
        try:
            return await self.client.async_set_device_properties(device_serial, properties)
        except HomerunAuthError:
            await self._async_reauth()
            return await self.client.async_set_device_properties(device_serial, properties)

    async def async_fetch_ez_token(self) -> Dict[str, Any]:
        """Fetch a fresh Ezviz token on demand. Does not poll or refresh in the background."""
        try:
            token_data = await self.client.async_get_ez_token()
        except HomerunAuthError:
            await self._async_reauth()
            token_data = await self.client.async_get_ez_token()

        if not token_data.get("accessToken"):
            detail = self.client.last_stream_error or "响应中没有 accessToken"
            raise HomerunApiError(f"无法取得萤石鉴权 Token: {detail}")

        self.ez_token_data = token_data
        return token_data

    async def async_invoke_service(
        self, device_serial: str, service_id: str, params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Invoke a device service with automatic re-auth on token expiration."""
        try:
            return await self.client.async_invoke_service(device_serial, service_id, params)
        except HomerunAuthError:
            await self._async_reauth()
            return await self.client.async_invoke_service(device_serial, service_id, params)
