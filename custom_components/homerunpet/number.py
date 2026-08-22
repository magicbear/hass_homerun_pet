"""Number platform for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable, Dict, List, Optional

from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import HomerunDataUpdateCoordinator
from .entity import HomerunBaseEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class HomerunNumberEntityDescription(NumberEntityDescription):
    """Description for Homerun number entities."""

    property_key: str = ""
    value_fn: Callable[[Dict[str, Any]], Optional[float]] = lambda p: None


NUMBER_DESCRIPTIONS: List[HomerunNumberEntityDescription] = [
    HomerunNumberEntityDescription(
        key="lamp_brightness",
        name="灯光亮度",
        property_key="lamp_brightness",
        native_min_value=1,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        icon="mdi:brightness-6",
        value_fn=lambda p: p.get("lamp_brightness"),
    ),
    HomerunNumberEntityDescription(
        key="portion",
        name="出粮份数设定",
        property_key="portion",
        native_min_value=1,
        native_max_value=10,
        native_step=1,
        native_unit_of_measurement="份",
        mode=NumberMode.BOX,
        icon="mdi:counter",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda p: p.get("portion", 1),
    ),
    HomerunNumberEntityDescription(
        key="countdown_set",
        name="工作倒计时设定",
        property_key="countdown_set",
        native_min_value=1,
        native_max_value=180,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.BOX,
        icon="mdi:timer-cog-outline",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda p: p.get("countdown_set"),
    ),
    HomerunNumberEntityDescription(
        key="speaker_volume",
        name="摄像机扬声器音量",
        property_key="speaker_volume",
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        native_unit_of_measurement=PERCENTAGE,
        mode=NumberMode.SLIDER,
        icon="mdi:volume-high",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda p: p.get("speaker_volume", 50),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homerun number entities."""
    coordinator: HomerunDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: List[HomerunNumber] = []
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
            model_services = {
                s.get("identifier")
                for s in thing_model.get("services", [])
                if isinstance(s, dict)
            }

            for desc in NUMBER_DESCRIPTIONS:
                if desc.key == "portion":
                    if categ in ("FeedingTrough", "Feeder", "FeedRackCamera") or "feed_plan" in model_props or "remote_feed" in model_services:
                        entities.append(HomerunNumber(coordinator, serial, desc))
                elif desc.property_key in props or desc.property_key in model_props:
                    entities.append(HomerunNumber(coordinator, serial, desc))

    async_add_entities(entities)


class HomerunNumber(HomerunBaseEntity, NumberEntity):
    """Representation of a Homerun number entity."""

    entity_description: HomerunNumberEntityDescription

    def __init__(
        self,
        coordinator: HomerunDataUpdateCoordinator,
        serial: str,
        description: HomerunNumberEntityDescription,
    ) -> None:
        """Initialize the number entity."""
        super().__init__(coordinator, serial, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> Optional[float]:
        """Return the entity value."""
        val = self.entity_description.value_fn(self.properties)
        return float(val) if val is not None else None

    async def async_set_native_value(self, value: float) -> None:
        """Set new value."""
        prop_key = self.entity_description.property_key
        int_val = int(value)
        await self.coordinator.client.async_set_device_properties(
            self.serial, {prop_key: int_val}
        )
        self.properties[prop_key] = int_val
        self.async_write_ha_state()
        await self.coordinator.async_request_refresh()
