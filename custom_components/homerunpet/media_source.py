"""Media Source implementation for Homerunpet feeding behavior and dynamic logs."""
from __future__ import annotations

import datetime
import logging
from typing import Any, Dict, List, Optional

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source.error import MediaSourceError, Unresolvable
from homeassistant.components.media_source.models import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Map raw event titles from Homerun cloud to user-friendly names
TITLE_MAP = {
    "petFeeder_text_successfullyProducedXPortionsOfGrainTimer": "定时出粮",
    "petFeeder_text_successfullyProducedXPortionsOfGrainRemote": "立即出粮",
    "petFeeder_text_PetEatFoodEvent": "宠物进食",
    "petFeeder_text_PetShowEvent": "靠近感应",
    "petFeeder_text_GeneralEvent": "喂食器动态",
}


def _format_event_title(item: Dict[str, Any]) -> str:
    """Format dynamic item into a human-readable title."""
    time_val = item.get("time", "")
    time_str = time_val.split(" ")[-1] if " " in time_val else time_val
    body = item.get("body") or {}
    data = body.get("data") or {}
    children = data.get("children") or []

    parts = []
    for c in children:
        c_title = c.get("title", "")
        c_data = c.get("data") or {}
        pet_list = c.get("petList") or []
        pet_name = pet_list[0].get("nikename") if pet_list else "宠物"

        if "successfullyProduced" in c_title or "PortionsOfGrain" in c_title:
            portions = c_data.get("x", "1")
            parts.append(f"🍲 出粮 {portions} 份")
        elif "PetEatFoodEvent" in c_title:
            duration = data.get("x", "")
            dur_str = f" ({duration}秒)" if duration else ""
            parts.append(f"🐱 {pet_name} 进食{dur_str}")
        elif "PetShowEvent" in c_title:
            parts.append(f"🐾 {pet_name} 现身")
        else:
            mapped = TITLE_MAP.get(c_title, c_title)
            parts.append(mapped)

    if parts:
        desc = " · ".join(parts)
    else:
        raw_title = body.get("title", "动态记录")
        desc = TITLE_MAP.get(raw_title, raw_title)

    return f"[{time_str}] {desc}"


async def async_get_media_source(hass: HomeAssistant) -> MediaSource:
    """Set up Homerunpet media source."""
    return HomerunMediaSource(hass)


class HomerunMediaSource(MediaSource):
    """Media source provider for Homerunpet device event history and media."""

    name: str = "Homerunpet (霍曼宠物)"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the media source."""
        super().__init__(DOMAIN)
        self.hass = hass

    def _get_coordinator(self):
        """Get the active Homerunpet coordinator."""
        if DOMAIN not in self.hass.data:
            return None
        entries = self.hass.data[DOMAIN]
        if not entries:
            return None
        return next(iter(entries.values()), None)

    async def async_browse_media(
        self,
        item: MediaSourceItem,
    ) -> BrowseMediaSource:
        """Browse Homerunpet media hierarchy."""
        coordinator = self._get_coordinator()
        if not coordinator:
            raise MediaSourceError("Homerunpet integration is not loaded.")

        identifier = item.identifier or ""
        parts = identifier.strip("/").split("/") if identifier else []

        # 1. Root level -> list camera & feeder devices
        if not identifier or len(parts) == 0 or parts == [""]:
            return self._build_root_browse(coordinator)

        serial = parts[0]
        dev_data = coordinator.data.get(serial) if coordinator.data else None
        dev = dev_data.get("device", {}) if dev_data else {}
        dev_name = dev.get("deviceName", f"设备 {serial}")

        # 2. Device level -> list date folders (last 7 days)
        if len(parts) == 1:
            return self._build_device_dates_browse(serial, dev_name)

        # 3. Date level -> list dynamic events for that date
        if len(parts) == 2:
            do_date = parts[1]
            return await self._build_date_events_browse(coordinator, serial, dev_name, do_date)

        # 4. Single event level
        if len(parts) >= 3:
            do_date = parts[1]
            event_id = parts[2]
            return await self._build_single_event_browse(coordinator, serial, dev_name, do_date, event_id)

        raise MediaSourceError(f"Unknown media path: {identifier}")

    def _build_root_browse(self, coordinator) -> BrowseMediaSource:
        """Build root directory listing all compatible devices."""
        children: List[BrowseMediaSource] = []

        if coordinator.data:
            for serial, dev_data in coordinator.data.items():
                dev = dev_data.get("device", {})
                dev_name = dev.get("deviceName", f"霍曼设备 {serial}")
                pic_url = dev.get("pic") or dev.get("pic1")

                children.append(
                    BrowseMediaSource(
                        domain=DOMAIN,
                        identifier=serial,
                        media_class=MediaClass.DIRECTORY,
                        media_content_type=MediaType.APP,
                        title=dev_name,
                        can_play=False,
                        can_expand=True,
                        thumbnail=pic_url,
                    )
                )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.APP,
            title="Homerunpet (霍曼智能宠物)",
            can_play=False,
            can_expand=True,
            children=children,
        )

    def _build_device_dates_browse(self, serial: str, dev_name: str) -> BrowseMediaSource:
        """Build date folder listing for a device."""
        children: List[BrowseMediaSource] = []
        today = datetime.date.today()

        for day_offset in range(7):
            cur_date = today - datetime.timedelta(days=day_offset)
            date_str = cur_date.strftime("%Y-%m-%d")

            if day_offset == 0:
                label = f"📅 今天 ({date_str})"
            elif day_offset == 1:
                label = f"📅 昨天 ({date_str})"
            elif day_offset == 2:
                label = f"📅 前天 ({date_str})"
            else:
                weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][cur_date.weekday()]
                label = f"📅 {date_str} ({weekday_cn})"

            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{serial}/{date_str}",
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.APP,
                    title=label,
                    can_play=False,
                    can_expand=True,
                )
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=serial,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.APP,
            title=f"🐾 {dev_name} - 进食行为与动态记录",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _build_date_events_browse(
        self, coordinator, serial: str, dev_name: str, do_date: str
    ) -> BrowseMediaSource:
        """Fetch and build dynamic events list for a given date."""
        dynamics = await coordinator.client.async_get_device_dynamics(serial, do_date, page=1, limit=50)
        children: List[BrowseMediaSource] = []

        for item in dynamics:
            event_id = str(item.get("id", ""))
            event_title = _format_event_title(item)
            body = item.get("body") or {}
            data = body.get("data") or {}
            video_info = data.get("video") or {}
            storage_id = video_info.get("storageId", "")
            # HomeRun's app treats cloudVideoStatus == 0 as an expired/image-only
            # event and only shows storageUrl as a still.  Asking Ezviz for cloud
            # playback in that state returns a short ErrCode/9053 placeholder
            # video whose frame misleadingly says the codec is not H.264.
            has_video = bool(
                video_info.get("cloudVideoStatus") == 1
                and video_info.get("deviceSerial")
                and video_info.get("startTime")
                and video_info.get("endTime")
            )

            # Resolve snapshot URL for thumbnail display
            thumbnail_url = None
            if storage_id:
                thumbnail_url = await coordinator.client.async_get_storage_download_url(storage_id)

            if not thumbnail_url:
                pet_list = item.get("petList") or []
                thumbnail_url = pet_list[0].get("avatarUrl") if pet_list else None

            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=f"{serial}/{do_date}/{event_id}",
                    media_class=MediaClass.VIDEO if has_video else MediaClass.IMAGE,
                    media_content_type=MediaType.VIDEO if has_video else MediaType.IMAGE,
                    title=event_title,
                    can_play=has_video or bool(thumbnail_url),
                    can_expand=False,
                    thumbnail=thumbnail_url,
                )
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{serial}/{do_date}",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.APP,
            title=f"📋 {do_date} 动态记录 ({len(children)}条)",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _build_single_event_browse(
        self, coordinator, serial: str, dev_name: str, do_date: str, event_id: str
    ) -> BrowseMediaSource:
        """Build single dynamic event item."""
        dynamics = await coordinator.client.async_get_device_dynamics(serial, do_date, page=1, limit=50)
        matched = next((d for d in dynamics if str(d.get("id")) == event_id), None)

        title = _format_event_title(matched) if matched else f"事件 {event_id}"
        thumbnail_url = None
        has_video = False
        if matched:
            body = matched.get("body") or {}
            data = body.get("data") or {}
            video_info = data.get("video") or {}
            storage_id = video_info.get("storageId")
            has_video = bool(
                video_info.get("cloudVideoStatus") == 1
                and video_info.get("deviceSerial")
                and video_info.get("startTime")
                and video_info.get("endTime")
            )
            if storage_id:
                thumbnail_url = await coordinator.client.async_get_storage_download_url(storage_id)

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=f"{serial}/{do_date}/{event_id}",
            media_class=MediaClass.VIDEO if has_video else MediaClass.IMAGE,
            media_content_type=MediaType.VIDEO if has_video else MediaType.IMAGE,
            title=title,
            can_play=has_video or bool(thumbnail_url),
            can_expand=False,
            thumbnail=thumbnail_url,
        )

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a dynamic event item to a viewable snapshot URL."""
        coordinator = self._get_coordinator()
        if not coordinator:
            raise Unresolvable("Homerunpet coordinator is not loaded.")

        parts = item.identifier.strip("/").split("/")
        if len(parts) < 3:
            raise Unresolvable(f"Invalid media item identifier: {item.identifier}")

        serial, do_date, event_id = parts[0], parts[1], parts[2]
        dynamics = await coordinator.client.async_get_device_dynamics(serial, do_date, page=1, limit=50)
        matched = next((d for d in dynamics if str(d.get("id")) == event_id), None)

        if not matched:
            raise Unresolvable(f"Event {event_id} not found on {do_date}")

        body = matched.get("body") or {}
        data = body.get("data") or {}
        video_info = data.get("video") or {}
        storage_id = video_info.get("storageId")

        camera_serial = video_info.get("deviceSerial")
        start_time = video_info.get("startTime")
        stop_time = video_info.get("endTime")
        channel = int(video_info.get("channelNo") or 1)
        if (
            video_info.get("cloudVideoStatus") == 1
            and camera_serial
            and start_time
            and stop_time
        ):
            token_data = coordinator.ez_token_data or {}
            playback_url = await coordinator.client.async_get_ezviz_live_url(
                str(camera_serial),
                token_data,
                channel,
                int(start_time),
                int(stop_time),
            )
            if not playback_url:
                token_data = await coordinator.client.async_get_ez_token()
                coordinator.ez_token_data = token_data
                playback_url = await coordinator.client.async_get_ezviz_live_url(
                    str(camera_serial),
                    token_data,
                    channel,
                    int(start_time),
                    int(stop_time),
                )
            if playback_url:
                # The HA media-browser frontend only routes this exact MIME type
                # through its hls.js player.  The equally valid Apple MIME type
                # is treated as an unsupported generic application payload.
                return PlayMedia(playback_url, "application/x-mpegURL")

        if storage_id:
            download_url = await coordinator.client.async_get_storage_download_url(storage_id)
            if download_url:
                return PlayMedia(download_url, "image/jpeg")

        # Fallback to device snapshot or product picture
        dev_data = coordinator.data.get(serial, {}) if coordinator.data else {}
        dev = dev_data.get("device", {})
        pic_url = dev.get("pic") or dev.get("pic1")
        if pic_url:
            return PlayMedia(pic_url, "image/png")

        raise Unresolvable("No media snapshot available for this event.")
