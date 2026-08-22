"""Switch platform for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable, Dict, List

from homeassistant.components.switch import (
    SwitchDeviceClass,
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HomerunDataUpdateCoordinator
from .entity import HomerunBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HomerunSwitchEntityDescription(SwitchEntityDescription):
    """Description for Homerun switch entities."""

    property_key: str = ""
    is_on_fn: Callable[[Dict[str, Any]], bool] = lambda p: False


SWITCH_DESCRIPTIONS: List[HomerunSwitchEntityDescription] = [
    HomerunSwitchEntityDescription(
        key="power",
        translation_key="power",
        property_key="switch",
        device_class=SwitchDeviceClass.SWITCH,
        is_on_fn=lambda p: bool(p.get("switch")),
    ),
    HomerunSwitchEntityDescription(
        key="child_lock",
        translation_key="child_lock",
        property_key="child_lock",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:account-lock",
        is_on_fn=lambda p: bool(p.get("child_lock")),
    ),
    HomerunSwitchEntityDescription(
        key="night_mode",
        translation_key="night_mode",
        property_key="night_mode",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:weather-night",
        is_on_fn=lambda p: bool(p.get("night_mode")),
    ),
    HomerunSwitchEntityDescription(
        key="auto_clean",
        translation_key="auto_clean",
        property_key="auto_clean",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:broom",
        is_on_fn=lambda p: bool(p.get("auto_clean")),
    ),
    HomerunSwitchEntityDescription(
        key="auto_cover",
        translation_key="auto_cover",
        property_key="auto_cover_switch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:shield-check",
        is_on_fn=lambda p: bool(p.get("auto_cover_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="auto_refill",
        translation_key="auto_refill",
        property_key="auto_refill_switch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:package-variant-closed",
        is_on_fn=lambda p: bool(p.get("auto_refill_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="kitten_mode",
        translation_key="kitten_mode",
        property_key="kitten_mode_switch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:cat",
        is_on_fn=lambda p: bool(p.get("kitten_mode_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="lamp",
        translation_key="lamp",
        property_key="lamp_switch",
        icon="mdi:lightbulb",
        is_on_fn=lambda p: bool(p.get("lamp_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="deep_clean",
        translation_key="deep_clean",
        property_key="deep_clean_switch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:shimmer",
        is_on_fn=lambda p: bool(p.get("deep_clean_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="fan_switch",
        translation_key="fan_switch",
        property_key="fan_switch",
        icon="mdi:fan",
        is_on_fn=lambda p: bool(p.get("fan_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="mute",
        translation_key="mute",
        property_key="mute",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:volume-mute",
        is_on_fn=lambda p: bool(p.get("mute")),
    ),
    HomerunSwitchEntityDescription(
        key="feed_detect",
        translation_key="feed_detect",
        property_key="feed_detect_switch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:radar",
        is_on_fn=lambda p: bool(p.get("feed_detect_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="clog_detect",
        translation_key="clog_detect",
        property_key="clog_detect_switch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:alert-circle-check-outline",
        is_on_fn=lambda p: bool(p.get("clog_detect_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="next_feed_switch",
        translation_key="next_feed_switch",
        property_key="next_feed_switch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:food-drumstick-outline",
        is_on_fn=lambda p: bool(p.get("next_feed_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="camera_switch",
        translation_key="camera_switch",
        property_key="camera_switch",
        icon="mdi:camera",
        is_on_fn=lambda p: bool(p.get("camera_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="mic_switch",
        translation_key="mic_switch",
        property_key="mic_switch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:microphone",
        is_on_fn=lambda p: bool(p.get("mic_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="osd_time_switch",
        translation_key="osd_time_switch",
        property_key="osd_time_switch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:clock-digital",
        is_on_fn=lambda p: bool(p.get("osd_time_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="object_frame_switch",
        translation_key="object_frame_switch",
        property_key="object_frame_switch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:vector-square",
        is_on_fn=lambda p: bool(p.get("object_frame_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="detect_presence_switch",
        translation_key="detect_presence_switch",
        property_key="detect_presence_switch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:motion-sensor",
        is_on_fn=lambda p: bool(p.get("detect_presence_switch")),
    ),
    HomerunSwitchEntityDescription(
        key="detect_behavior_switch",
        translation_key="detect_behavior_switch",
        property_key="detect_behavior_switch",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:video-vintage",
        is_on_fn=lambda p: bool(p.get("detect_behavior_switch")),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homerun switch entities."""
    coordinator: HomerunDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: List[HomerunSwitch] = []
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
            for desc in SWITCH_DESCRIPTIONS:
                # Add entity only if property exists in device properties or thing model
                if desc.property_key in props or desc.property_key in model_props:
                    entities.append(HomerunSwitch(coordinator, serial, desc))

    async_add_entities(entities)


class HomerunSwitch(HomerunBaseEntity, SwitchEntity):
    """Representation of a Homerun switch entity."""

    entity_description: HomerunSwitchEntityDescription

    def __init__(
        self,
        coordinator: HomerunDataUpdateCoordinator,
        serial: str,
        description: HomerunSwitchEntityDescription,
    ) -> None:
        """Initialize the switch."""
        super().__init__(coordinator, serial, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        return self.entity_description.is_on_fn(self.properties)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        prop_key = self.entity_description.property_key
        await self.coordinator.client.async_set_device_properties(
            self.serial, {prop_key: True}
        )
        self.properties[prop_key] = True
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        prop_key = self.entity_description.property_key
        await self.coordinator.client.async_set_device_properties(
            self.serial, {prop_key: False}
        )
        self.properties[prop_key] = False
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
