"""Camera platform for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from homeassistant.components.camera import (
    Camera,
    CameraCapabilities,
    CameraEntityFeature,
)
from homeassistant.components.camera.const import StreamType
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CAMERA_CATEGORIES, DOMAIN
from .coordinator import HomerunDataUpdateCoordinator
from .entity import HomerunBaseEntity
from .homerun_api import HomerunApiError, camera_serial_from_device, is_camera_device

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homerun camera entities."""
    coordinator: HomerunDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: List[HomerunCamera] = []
    if coordinator.data:
        for serial, dev_data in coordinator.data.items():
            dev = dev_data.get("device", {})
            props = dev_data.get("properties", {})
            thing_model = coordinator.client.get_device_thing_model(dev)
            model_props = {
                p.get("identifier")
                for p in thing_model.get("properties", [])
                if isinstance(p, dict)
            }

            if is_camera_device(dev, props, model_props, CAMERA_CATEGORIES):
                entities.append(HomerunCamera(coordinator, serial))

    async_add_entities(entities)


class HomerunCamera(HomerunBaseEntity, Camera):
    """Representation of a Homerun smart camera."""

    _attr_supported_features = CameraEntityFeature.ON_OFF | CameraEntityFeature.STREAM
    _attr_brand = "Homerunpet (霍曼)"
    _attr_use_stream_for_stills = False

    def __init__(
        self,
        coordinator: HomerunDataUpdateCoordinator,
        serial: str,
    ) -> None:
        """Initialize the camera."""
        HomerunBaseEntity.__init__(self, coordinator, serial, "camera")
        Camera.__init__(self)
        self._attr_name = "摄像头实时画面"
        self._attr_icon = "mdi:cctv"
        self._cached_image: Optional[bytes] = None

    @property
    def use_stream_for_stills(self) -> bool:
        """Do not use stream worker for stills."""
        return False

    @property
    def camera_capabilities(self) -> CameraCapabilities:
        """Expose only WebRTC because the source is transcoded by go2rtc.

        Home Assistant's HLS pipeline cannot consume go2rtc's ``ffmpeg:``
        producer syntax. Advertising HLS makes the frontend select that broken
        path even though the go2rtc WebRTC provider can play it correctly.
        """
        return CameraCapabilities({StreamType.WEB_RTC})

    @property
    def camera_serial(self) -> str:
        """Return the Ezviz child serial used by the official app."""
        return camera_serial_from_device(self.device_raw_data, self.serial)

    async def stream_source(self) -> Optional[str]:
        """Return a standard stream URL for HA Stream and its go2rtc provider."""
        token_data = self.coordinator.ez_token_data or {}
        source = await self.coordinator.client.async_get_ezviz_live_url(
            self.camera_serial, token_data
        )
        if source:
            return f"ffmpeg:{source}#video=h264#audio=opus"

        # The Ezviz token can expire independently from the HomeRun login token.
        token_data = await self.coordinator.client.async_get_ez_token()
        self.coordinator.ez_token_data = token_data
        if not token_data.get("accessToken"):
            detail = self.coordinator.client.last_stream_error or "响应中没有 accessToken"
            raise HomerunApiError(f"无法取得萤石鉴权 Token: {detail}")
        source = await self.coordinator.client.async_get_ezviz_live_url(
            self.camera_serial, token_data
        )
        if source:
            return f"ffmpeg:{source}#video=h264#audio=opus"

        detail = self.coordinator.client.last_stream_error or "未知错误"
        raise HomerunApiError(f"无法取得萤石直播地址: {detail}")

    async def async_camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Return bytes of camera image or snapshot."""
        if self._cached_image:
            return self._cached_image

        pic_url = self.device_raw_data.get("pic") or self.device_raw_data.get("pic1")
        if pic_url:
            try:
                session = await self.coordinator.client._get_session()
                async with session.get(pic_url, timeout=aiohttp.ClientTimeout(total=3)) as resp:
                    if resp.status == 200:
                        self._cached_image = await resp.read()
                        return self._cached_image
            except Exception as err:
                _LOGGER.debug("Failed to fetch camera snapshot for %s: %s", self.serial, err)

        # Fast fallback 1x1 JPEG so HA /api/camera_proxy never blocks or raises HTTP 500
        return (
            b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x01\x00H\x00H\x00\x00\xff\xdb\x00C\x00"
            b"\x08\x06\x06\x07\x06\x05\x08\x07\x07\x07\t\t\x08\n\x0c\x14\r\x0c\x0b\x0b\x0c\x19\x12"
            b"\x13\x0f\x14\x1d\x1a\x1f\x1e\x1d\x1a\x1c\x1c $.' \",#\x1c\x1c(7),01444\x1f'9=82<.342"
            b"\xff\xc0\x00\x0b\x08\x00\x01\x00\x01\x01\x01\x11\x00\xff\xc4\x00\x1f\x00\x00\x01\x05"
            b"\x01\x01\x01\x01\x01\x01\x00\x00\x00\x00\x00\x00\x00\x00\x01\x02\x03\x04\x05\x06\x07"
            b"\x08\t\n\x0b\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xbf\x00\xff\xd9"
        )

    @property
    def is_on(self) -> bool:
        """Return True if camera is on."""
        return bool(self.get_property("camera_switch", True))

    @property
    def is_recording(self) -> bool:
        """Return True if pet behavior / activity recording is enabled."""
        return bool(self.get_property("detect_behavior_switch", False))

    @property
    def motion_detection_enabled(self) -> bool:
        """Return True if pet presence/motion detection is enabled."""
        return bool(self.get_property("detect_presence_switch", True))

    async def async_turn_on(self) -> None:
        """Turn on camera."""
        await self.coordinator.client.async_set_device_properties(
            self.serial, {"camera_switch": True}
        )
        self.properties["camera_switch"] = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off camera."""
        await self.coordinator.client.async_set_device_properties(
            self.serial, {"camera_switch": False}
        )
        self.properties["camera_switch"] = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_enable_motion_detection(self) -> None:
        """Enable pet motion / presence detection."""
        await self.coordinator.client.async_set_device_properties(
            self.serial, {"detect_presence_switch": True}
        )
        self.properties["detect_presence_switch"] = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_disable_motion_detection(self) -> None:
        """Disable pet motion / presence detection."""
        await self.coordinator.client.async_set_device_properties(
            self.serial, {"detect_presence_switch": False}
        )
        self.properties["detect_presence_switch"] = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    @property
    def extra_state_attributes(self) -> Dict[str, Any]:
        """Return camera specific extra attributes."""
        attrs: Dict[str, Any] = {}
        if "ir_mode" in self.properties:
            attrs["night_vision_mode"] = self.properties.get("ir_mode")
        if "mic_switch" in self.properties:
            attrs["mic_enabled"] = bool(self.properties.get("mic_switch"))
        if "speaker_volume" in self.properties:
            attrs["speaker_volume"] = self.properties.get("speaker_volume")
        if "osd_time_switch" in self.properties:
            attrs["osd_timestamp"] = bool(self.properties.get("osd_time_switch"))
        if "object_frame_switch" in self.properties:
            attrs["ai_object_bounding_box"] = bool(self.properties.get("object_frame_switch"))

        ez_data = self.coordinator.ez_token_data or {}
        if ez_data:
            attrs["ezviz_app_key"] = ez_data.get("ysAppKey")
            attrs["ezviz_domain"] = ez_data.get("ysDomain")
        attrs["device_serial"] = self.serial
        attrs["camera_serial"] = self.camera_serial
        return attrs
