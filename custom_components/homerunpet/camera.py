"""Camera platform for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

import aiohttp

from homeassistant.components.camera import (
    Camera,
    CameraEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CATEGORY_CAMERA,
    CATEGORY_CAT_LITTER_BOX,
    CATEGORY_FEEDER,
    CATEGORY_FEED_RACK_CAMERA,
    CATEGORY_WATER_FOUNTAIN,
    DOMAIN,
)
from .coordinator import HomerunDataUpdateCoordinator
from .entity import HomerunBaseEntity
from .homerun_api import HomerunApiError

_LOGGER = logging.getLogger(__name__)

CAMERA_CATEGORIES = {
    CATEGORY_FEED_RACK_CAMERA,
    CATEGORY_CAMERA,
    "FeedRackCamera",
    "C01_Camera",
    "SideboardCamera",
    "WaterCamera",
}


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
            categ = dev.get("categ", "")
            thing_model = coordinator.client.get_device_thing_model(dev)
            model_props = {
                p.get("identifier")
                for p in thing_model.get("properties", [])
                if isinstance(p, dict)
            }

            # Check if device is actually a camera device (e.g. video feeder, smart rack camera, etc.)
            is_camera = (
                categ in CAMERA_CATEGORIES
                or dev.get("isCamera") == 1
                or bool(dev.get("cameraList"))
                or "camera_switch" in props
                or "camera_switch" in model_props
                or "ir_mode" in props
                or "ir_mode" in model_props
            )

            if is_camera:
                entities.append(HomerunCamera(coordinator, serial))

    async_add_entities(entities)


class HomerunCamera(HomerunBaseEntity, Camera):
    """Representation of a Homerun smart camera."""

    _attr_supported_features = CameraEntityFeature.ON_OFF | CameraEntityFeature.STREAM
    _attr_brand = "Homerunpet (霍曼)"

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
    def camera_serial(self) -> str:
        """Return the Ezviz child serial used by the official app."""
        camera_list = self.device_raw_data.get("cameraList") or []
        if camera_list and isinstance(camera_list[0], dict):
            child_serial = camera_list[0].get("deviceSerial")
            if child_serial:
                return str(child_serial)
        return self.serial

    async def stream_source(self) -> Optional[str]:
        """Return a standard stream URL for HA Stream and its go2rtc provider."""
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
        """Return bytes of camera image or snapshot."""
        if self._cached_image:
            return self._cached_image

        pic_url = self.device_raw_data.get("pic") or self.device_raw_data.get("pic1")
        if not pic_url:
            return None

        try:
            session = await self.coordinator.client._get_session()
            async with session.get(pic_url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    self._cached_image = await resp.read()
                    return self._cached_image
        except Exception as err:
            _LOGGER.debug("Failed to fetch camera snapshot for %s: %s", self.serial, err)

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
