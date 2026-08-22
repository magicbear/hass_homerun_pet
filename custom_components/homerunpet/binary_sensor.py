"""Binary sensor platform for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable, Dict, List

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
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
class HomerunBinarySensorEntityDescription(BinarySensorEntityDescription):
    """Description for Homerun binary sensor entities."""

    property_key: str = ""
    is_on_fn: Callable[[Dict[str, Any]], bool] = lambda p: False


BINARY_SENSOR_DESCRIPTIONS: List[HomerunBinarySensorEntityDescription] = [
    HomerunBinarySensorEntityDescription(
        key="cat_nearby",
        name="猫咪靠近感应",
        property_key="cat_nearby",
        device_class=BinarySensorDeviceClass.MOTION,
        icon="mdi:cat",
        is_on_fn=lambda p: bool(p.get("cat_nearby")),
    ),
    HomerunBinarySensorEntityDescription(
        key="cat_inside",
        name="猫咪进入仓内",
        property_key="cat_inside",
        device_class=BinarySensorDeviceClass.OCCUPANCY,
        icon="mdi:home-heart",
        is_on_fn=lambda p: bool(p.get("cat_inside")),
    ),
    HomerunBinarySensorEntityDescription(
        key="waste_bin_full",
        name="集便仓满告警",
        property_key="waste_bin_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:delete-alert",
        is_on_fn=lambda p: bool(
            p.get("waste_bin_status") == 1
            or p.get("waste_bin_full_status") == 1
            or p.get("waste_bin_status") is True
        ),
    ),
    HomerunBinarySensorEntityDescription(
        key="food_empty",
        name="粮桶缺粮预警",
        property_key="food_remain_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:food-drumstick-off",
        # The official app reads this value from the device's ``LackFood``
        # boolean property: false/0 means normal and true/1 means low food.
        is_on_fn=lambda p: p.get("food_remain_status") in (True, 1, "1", "true", "True"),
    ),
    HomerunBinarySensorEntityDescription(
        key="power_connected",
        name="电源适配器连接",
        property_key="power_connected",
        device_class=BinarySensorDeviceClass.PLUG,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda p: bool(p.get("power_connected")),
    ),
    HomerunBinarySensorEntityDescription(
        key="battery_present",
        name="备用电池在位",
        property_key="battery_present",
        device_class=BinarySensorDeviceClass.BATTERY_CHARGING,
        entity_category=EntityCategory.DIAGNOSTIC,
        is_on_fn=lambda p: bool(p.get("battery_present")),
    ),
    HomerunBinarySensorEntityDescription(
        key="litter_low",
        name="猫砂过低预警",
        property_key="toilet_remain_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-circle-outline",
        is_on_fn=lambda p: bool(p.get("toilet_remain_status") == 1 or p.get("refill_remain_status") == 1),
    ),
    HomerunBinarySensorEntityDescription(
        key="feed_outlet_block",
        name="出粮口堵粮异常",
        property_key="feed_outlet_status",
        device_class=BinarySensorDeviceClass.PROBLEM,
        icon="mdi:alert-octagon",
        is_on_fn=lambda p: bool(p.get("feed_outlet_status") == 1),
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homerun binary sensor entities."""
    coordinator: HomerunDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: List[HomerunBinarySensor] = []
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
            for desc in BINARY_SENSOR_DESCRIPTIONS:
                if desc.property_key in props or desc.property_key in model_props:
                    entities.append(HomerunBinarySensor(coordinator, serial, desc))

    async_add_entities(entities)


class HomerunBinarySensor(HomerunBaseEntity, BinarySensorEntity):
    """Representation of a Homerun binary sensor."""

    entity_description: HomerunBinarySensorEntityDescription

    def __init__(
        self,
        coordinator: HomerunDataUpdateCoordinator,
        serial: str,
        description: HomerunBinarySensorEntityDescription,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, serial, description.key)
        self.entity_description = description

    @property
    def is_on(self) -> bool:
        """Return True if the binary sensor is on."""
        return self.entity_description.is_on_fn(self.properties)
