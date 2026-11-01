"""Camera platform for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import Any, Dict, List, Optional

from go2rtc_client import Go2RtcRestClient

from homeassistant.components.camera import (
    Camera,
    CameraCapabilities,
    CameraEntityFeature,
)
from homeassistant.components.camera.const import StreamType
from homeassistant.components.go2rtc.const import HA_MANAGED_URL
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
        self._source_lock = asyncio.Lock()
        self._live_source: Optional[str] = None
        self._source_expires = 0.0
        relay_id = hashlib.sha256(serial.encode()).hexdigest()[:12]
        self._relay_name = f"homerunpet_relay_{relay_id}"

    @property
    def use_stream_for_stills(self) -> bool:
        """Do not use stream worker for stills."""
        return False

    @property
    def camera_capabilities(self) -> CameraCapabilities:
        """Use go2rtc for browser playback of the H.264 relay."""
        return CameraCapabilities({StreamType.WEB_RTC})

    @property
    def camera_serial(self) -> str:
        """Return the Ezviz child serial used by the official app."""
        return camera_serial_from_device(self.device_raw_data, self.serial)

    def _relay_client(self) -> Go2RtcRestClient:
        """Use the go2rtc instance managed by this Home Assistant."""
        config = self.hass.data.get("go2rtc")
        if config is None:
            raise HomerunApiError("Home Assistant go2rtc is not ready")
        return Go2RtcRestClient(config.session, config.url)

    async def stream_source(self) -> Optional[str]:
        """Expose a standard RTSP URL usable by HomeKit and HA alike.

        The upstream ffmpeg: producer syntax is interpreted only by go2rtc.
        HomeKit invokes FFmpeg directly, so register that producer internally
        and return its H.264 relay instead. Port 18554 belongs to HA's
        built-in go2rtc instance; an external go2rtc needs its own RTSP port.
        """
        async with self._source_lock:
            if not self._live_source or time.monotonic() >= self._source_expires:
                self._live_source = await self._async_cloud_stream_source()
                self._source_expires = time.monotonic() + 3000
            source = f"ffmpeg:{self._live_source}#video=h264#audio=opus"
            client = self._relay_client()
            streams = await client.streams.list()
            stream = streams.get(self._relay_name)
            if stream is None or not any(p.url == source for p in stream.producers):
                await client.streams.add(self._relay_name, [source])
            if self.hass.data["go2rtc"].url == HA_MANAGED_URL:
                return f"rtsp://127.0.0.1:18554/{self._relay_name}"
            # External go2rtc instances may use a different RTSP listener.
            # Preserve their existing WebRTC source until that port is configurable.
            return source

    async def _async_cloud_stream_source(self) -> str:
        """Resolve the expiring cloud source without exposing tokens in state."""
        token_data = self.coordinator.ez_token_data or {}
        source = await self.coordinator.client.async_get_ezviz_live_url(
            self.camera_serial, token_data
        )
        if source:
            return source

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
            return source

        detail = self.coordinator.client.last_stream_error or "未知错误"
        raise HomerunApiError(f"无法取得萤石直播地址: {detail}")

    async def async_camera_image(
        self, width: Optional[int] = None, height: Optional[int] = None
    ) -> Optional[bytes]:
        """Return a fresh frame from the same relay used for live video."""
        try:
            async with asyncio.timeout(20):
                await self.stream_source()
                return await self._relay_client().get_jpeg_snapshot(
                    self._relay_name, width, height
                )
        except Exception as err:
            # Cloud URLs contain credentials; log only the exception type.
            _LOGGER.warning("Camera snapshot failed: %s", type(err).__name__)
            return None

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
