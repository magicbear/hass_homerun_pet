"""Read-only services for the Homerunpet integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional, Tuple

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er

from .const import (
    ATTR_DEVICE_SERIAL,
    CAMERA_CATEGORIES,
    DOMAIN,
    SERVICE_GET_YS7_CREDENTIALS,
)
from .coordinator import HomerunDataUpdateCoordinator
from .homerun_api import (
    HomerunAuthError,
    HomerunConnectionError,
    HomerunError,
    build_ys7_credentials,
    camera_serial_from_device,
    is_camera_device,
)

_LOGGER = logging.getLogger(__name__)

SERVICE_GET_YS7_CREDENTIALS_SCHEMA = vol.Schema(
    {
        vol.Optional(ATTR_DEVICE_ID): vol.Any(cv.string, [cv.string]),
        vol.Optional(ATTR_ENTITY_ID): cv.entity_ids,
        vol.Optional(ATTR_DEVICE_SERIAL): cv.string,
    }
)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register domain services once."""
    if hass.services.has_service(DOMAIN, SERVICE_GET_YS7_CREDENTIALS):
        return

    async def _handle_get_ys7_credentials(call: ServiceCall) -> ServiceResponse:
        return await async_get_ys7_credentials(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_GET_YS7_CREDENTIALS,
        _handle_get_ys7_credentials,
        schema=SERVICE_GET_YS7_CREDENTIALS_SCHEMA,
        supports_response=SupportsResponse.ONLY,
    )


@callback
def async_unload_services(hass: HomeAssistant) -> None:
    """Remove domain services when the last config entry unloads."""
    if hass.data.get(DOMAIN):
        return
    if hass.services.has_service(DOMAIN, SERVICE_GET_YS7_CREDENTIALS):
        hass.services.async_remove(DOMAIN, SERVICE_GET_YS7_CREDENTIALS)


def _coordinators(hass: HomeAssistant) -> List[HomerunDataUpdateCoordinator]:
    data = hass.data.get(DOMAIN) or {}
    return [coord for coord in data.values() if isinstance(coord, HomerunDataUpdateCoordinator)]


def _unwrap_id(value: Any) -> Optional[str]:
    if isinstance(value, list):
        value = value[0] if value else None
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _serial_from_device_id(hass: HomeAssistant, device_id: str) -> Optional[str]:
    device = dr.async_get(hass).async_get(device_id)
    if not device:
        return None
    for domain, ident in device.identifiers:
        if domain == DOMAIN and ident:
            return str(ident)
    return None


def _serial_from_entity_id(hass: HomeAssistant, entity_id: str) -> Optional[str]:
    entry = er.async_get(hass).async_get(entity_id)
    if not entry or entry.platform != DOMAIN:
        return None
    if entry.device_id:
        serial = _serial_from_device_id(hass, entry.device_id)
        if serial:
            return serial
    unique_id = entry.unique_id or ""
    if "_" in unique_id:
        return unique_id.rsplit("_", 1)[0]
    return unique_id or None


def _match_serial(
    coordinator: HomerunDataUpdateCoordinator, serial: str
) -> Optional[Tuple[str, Dict[str, Any]]]:
    data = coordinator.data or {}
    if serial in data:
        return serial, data[serial]
    serial_l = serial.lower()
    for parent_serial, row in data.items():
        device = row.get("device") or {}
        candidates = {
            parent_serial,
            str(device.get("deviceSerial") or ""),
            camera_serial_from_device(row, parent_serial),
        }
        if any(item.lower() == serial_l for item in candidates if item):
            return parent_serial, row
    return None


def _find_row(
    hass: HomeAssistant, serial: str
) -> Tuple[HomerunDataUpdateCoordinator, str, Dict[str, Any]]:
    for coordinator in _coordinators(hass):
        matched = _match_serial(coordinator, serial)
        if matched:
            return coordinator, matched[0], matched[1]
    raise HomeAssistantError(f"未找到霍曼设备: {serial}")


def _iter_camera_rows(
    coordinator: HomerunDataUpdateCoordinator,
) -> List[Tuple[str, Dict[str, Any]]]:
    rows: List[Tuple[str, Dict[str, Any]]] = []
    for serial, row in (coordinator.data or {}).items():
        dev = row.get("device") or {}
        props = row.get("properties") or {}
        thing_model = coordinator.client.get_device_thing_model(dev)
        model_props = {
            p.get("identifier")
            for p in thing_model.get("properties", [])
            if isinstance(p, dict)
        }
        if is_camera_device(dev, props, model_props, CAMERA_CATEGORIES):
            rows.append((serial, row))
    return rows


def _resolve_target(
    hass: HomeAssistant, call: ServiceCall
) -> Tuple[HomerunDataUpdateCoordinator, str, Dict[str, Any]]:
    device_id = _unwrap_id(call.data.get(ATTR_DEVICE_ID))
    entity_ids = call.data.get(ATTR_ENTITY_ID) or []
    if isinstance(entity_ids, str):
        entity_ids = [entity_ids]
    device_serial = _unwrap_id(call.data.get(ATTR_DEVICE_SERIAL))

    serial = None
    if device_id:
        serial = _serial_from_device_id(hass, device_id)
        if not serial:
            raise HomeAssistantError(f"设备不属于霍曼宠物集成: {device_id}")
    elif entity_ids:
        serial = _serial_from_entity_id(hass, entity_ids[0])
        if not serial:
            raise HomeAssistantError(f"实体不属于霍曼宠物集成: {entity_ids[0]}")
    elif device_serial:
        serial = device_serial

    if serial:
        return _find_row(hass, serial)

    coordinators = _coordinators(hass)
    if not coordinators:
        raise HomeAssistantError("霍曼宠物集成尚未就绪")

    cameras: List[Tuple[HomerunDataUpdateCoordinator, str, Dict[str, Any]]] = []
    for coordinator in coordinators:
        for parent_serial, row in _iter_camera_rows(coordinator):
            cameras.append((coordinator, parent_serial, row))

    if len(cameras) == 1:
        return cameras[0]
    if not cameras:
        if len(coordinators) == 1 and coordinators[0].data:
            items = list(coordinators[0].data.items())
            if len(items) == 1:
                serial, row = items[0]
                return coordinators[0], serial, row
        raise HomeAssistantError("账号下没有摄像头设备，请指定 device_id 或 device_serial")
    raise HomeAssistantError(
        f"账号下有 {len(cameras)} 台摄像头，请指定 device_id、entity_id 或 device_serial"
    )


async def async_get_ys7_credentials(
    hass: HomeAssistant, call: ServiceCall
) -> ServiceResponse:
    """Fetch a fresh Ezviz token and return SRS-ready credentials."""
    coordinator, serial, row = _resolve_target(hass, call)
    try:
        token_data = await coordinator.async_fetch_ez_token()
    except HomerunAuthError as err:
        raise HomeAssistantError(f"霍曼账号认证失败: {err}") from err
    except HomerunConnectionError as err:
        raise HomeAssistantError(f"无法连接霍曼云: {err}") from err
    except HomerunError as err:
        raise HomeAssistantError(str(err)) from err

    payload = build_ys7_credentials(token_data, device_serial=serial, device=row)
    if not payload.get("access_token"):
        raise HomeAssistantError("萤石 accessToken 为空")
    if not payload.get("ys_app_key"):
        _LOGGER.warning("ezToken response did not include ysAppKey for %s", serial)
    _LOGGER.debug(
        "YS7 credentials issued serial=%s camera=%s domain=%s",
        serial,
        payload.get("camera_serial"),
        payload.get("ys_domain"),
    )
    return payload
