"""Button platform for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any, Callable, Dict, List

from homeassistant.components.button import (
    ButtonDeviceClass,
    ButtonEntity,
    ButtonEntityDescription,
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
class HomerunButtonEntityDescription(ButtonEntityDescription):
    """Description for Homerun button entities."""

    service_id: str = ""
    params: Dict[str, Any] = None


BUTTON_DESCRIPTIONS: List[HomerunButtonEntityDescription] = [
    HomerunButtonEntityDescription(
        key="remote_feed",
        name="立即喂食",
        service_id="remote_feed",
        icon="mdi:food-drumstick",
    ),
    HomerunButtonEntityDescription(
        key="desiccant_reset",
        name="重置干燥剂",
        service_id="desiccant_reset",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:water-percent",
    ),
    HomerunButtonEntityDescription(
        key="announce_feed_voice",
        name="播报出粮语音",
        service_id="announce_feed_voice",
        icon="mdi:bullhorn",
    ),
    HomerunButtonEntityDescription(
        key="temp_enable_camera",
        name="唤醒摄像机",
        service_id="temp_enable_camera",
        icon="mdi:cctv",
    ),
    HomerunButtonEntityDescription(
        key="remote_clean",
        name="立即清理猫砂",
        service_id="remote_clean",
        icon="mdi:broom",
    ),
    HomerunButtonEntityDescription(
        key="remote_level",
        name="平整猫砂",
        service_id="remote_level",
        icon="mdi:format-align-justify",
    ),
    HomerunButtonEntityDescription(
        key="remote_refill",
        name="立即补砂",
        service_id="remote_refill",
        icon="mdi:package-variant-plus",
    ),
    HomerunButtonEntityDescription(
        key="filter_reset",
        name="重置滤芯寿命",
        service_id="filter_reset",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:restart",
    ),
    HomerunButtonEntityDescription(
        key="waste_bin_reset",
        name="重置集便盒满状态",
        service_id="waste_bin_full_reset",
        entity_category=EntityCategory.CONFIG,
        icon="mdi:delete-restore",
    ),
    HomerunButtonEntityDescription(
        key="restart",
        name="重启设备",
        service_id="restart",
        device_class=ButtonDeviceClass.RESTART,
        entity_category=EntityCategory.CONFIG,
        icon="mdi:power-cycle",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Homerun button entities."""
    coordinator: HomerunDataUpdateCoordinator = hass.data[DOMAIN][entry.entry_id]

    entities: List[HomerunButton] = []
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

            for desc in BUTTON_DESCRIPTIONS:
                # Strictly filter buttons according to device capabilities
                if desc.key == "remote_feed":
                    if "remote_feed" in model_services or categ in ("FeedingTrough", "Feeder", "FeedRackCamera") or "feed_plan" in model_props or "feed_plan" in props:
                        entities.append(HomerunButton(coordinator, serial, desc))
                elif desc.key == "desiccant_reset":
                    if "desiccant_reset" in model_services or "desiccant_info" in props or "desiccant_info" in model_props:
                        entities.append(HomerunButton(coordinator, serial, desc))
                elif desc.key == "announce_feed_voice":
                    if "announce_feed_voice" in model_services:
                        entities.append(HomerunButton(coordinator, serial, desc))
                elif desc.key == "temp_enable_camera":
                    if "temp_enable_camera" in model_services:
                        entities.append(HomerunButton(coordinator, serial, desc))
                elif desc.key == "remote_clean":
                    if "remote_clean" in model_services or (categ in ("CatLitterBox",) and ("clean_plan" in model_props or "clean_plan" in props)):
                        entities.append(HomerunButton(coordinator, serial, desc))
                elif desc.key == "remote_level":
                    if "remote_level" in model_services or (categ in ("CatLitterBox",) and "remote_level" in model_services):
                        entities.append(HomerunButton(coordinator, serial, desc))
                elif desc.key == "remote_refill":
                    if "remote_refill" in model_services or "refill_remain_status" in props or "refill_remain_status" in model_props:
                        entities.append(HomerunButton(coordinator, serial, desc))
                elif desc.key == "filter_reset":
                    if "filter_reset" in model_services or "filter_life" in props or "filter_life" in model_props:
                        entities.append(HomerunButton(coordinator, serial, desc))
                elif desc.key == "waste_bin_reset":
                    if "waste_bin_status" in props or "waste_bin_status" in model_props or "waste_bin_full_reset" in model_services:
                        entities.append(HomerunButton(coordinator, serial, desc))
                elif desc.key == "restart":
                    if "restart" in model_services or "restart" in props:
                        entities.append(HomerunButton(coordinator, serial, desc))

    async_add_entities(entities)


class HomerunButton(HomerunBaseEntity, ButtonEntity):
    """Representation of a Homerun button."""

    entity_description: HomerunButtonEntityDescription

    def __init__(
        self,
        coordinator: HomerunDataUpdateCoordinator,
        serial: str,
        description: HomerunButtonEntityDescription,
    ) -> None:
        """Initialize the button."""
        super().__init__(coordinator, serial, description.key)
        self.entity_description = description

    async def async_press(self) -> None:
        """Handle the button press."""
        service_id = self.entity_description.service_id
        params = self.entity_description.params or {}

        # If it's remote_feed, check if user has set portion size in properties
        if service_id == "remote_feed":
            portion = self.get_property("portion", 1)
            params = {"portion": int(portion)}

        await self.coordinator.async_invoke_service(
            self.serial, service_id, params
        )
        await self.coordinator.async_request_refresh()
