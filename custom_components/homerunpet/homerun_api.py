"""Async Python Client for the Homerunpet (霍曼宠物) Cloud API."""
from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import os
import ssl
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from urllib.parse import urlsplit, urlunsplit

import aiohttp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from .const import (
    API_HOSTS,
    APP_ID,
    APP_KEY,
    DEFAULT_REGION,
    EZ_TOKEN_IV,
    MD5_SALT,
    REGION_CN,
)

_LOGGER = logging.getLogger(__name__)

_CACHED_THING_MODELS: Optional[Dict[str, Any]] = None


def load_cached_thing_models() -> Dict[str, Any]:
    """Load bundled thing_models.json into memory cache."""
    global _CACHED_THING_MODELS
    if _CACHED_THING_MODELS is not None:
        return _CACHED_THING_MODELS
    try:
        curr_dir = os.path.dirname(os.path.abspath(__file__))
        json_path = os.path.join(curr_dir, "thing_models.json")
        if os.path.exists(json_path):
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                _CACHED_THING_MODELS = data.get("data", {})
                return _CACHED_THING_MODELS
    except Exception as err:
        _LOGGER.warning("Could not load thing_models.json: %s", err)
    _CACHED_THING_MODELS = {}
    return _CACHED_THING_MODELS


class HomerunError(Exception):
    """Base error for Homerunpet API."""


class HomerunAuthError(HomerunError):
    """Authentication or token expired error."""


class HomerunConnectionError(HomerunError):
    """Network connection or timeout error."""


class HomerunApiError(HomerunError):
    """API business logic error."""


def hash_password(password: str) -> str:
    """Replicates com.homerunpet.common.MD5.MD5Pwd.

    MD5(appKey + password + "#q&8UT6eRV79ol4*")[7:27]
    """
    raw = f"{APP_KEY}{password}{MD5_SALT}"
    md5_hex = hashlib.md5(raw.encode("utf-8")).hexdigest()
    return md5_hex[7:27]


def param_sign(params: Dict[str, Any], timestamp: str) -> str:
    """Replicates com.homerunpet.engine.ApiClient.paramSign.

    TreeMap descending sort: key=value&... + appKey={APP_KEY}&timestamp={timestamp}
    SHA256 hash in hex.
    """
    sorted_keys = sorted(params.keys(), reverse=True)
    body_str = ""
    for k in sorted_keys:
        body_str += f"{k}={params[k]}&"
    sign_str = f"{body_str}appKey={APP_KEY}&timestamp={timestamp}"
    return hashlib.sha256(sign_str.encode("utf-8")).hexdigest()


def decrypt_ezviz_token(encrypted_token: str) -> str:
    """Decrypt the Ezviz access token exactly as the Android app does."""
    if not encrypted_token or encrypted_token.startswith("at."):
        return encrypted_token

    encrypted = base64.b64decode(encrypted_token, validate=True)
    decryptor = Cipher(
        algorithms.AES(APP_KEY.encode("utf-8")),
        modes.CBC(EZ_TOKEN_IV.encode("utf-8")),
    ).decryptor()
    padded = decryptor.update(encrypted) + decryptor.finalize()
    unpadder = PKCS7(algorithms.AES.block_size).unpadder()
    return (unpadder.update(padded) + unpadder.finalize()).decode("utf-8")


class HomerunApiClient:
    """Async API Client for Homerunpet cloud."""

    def __init__(
        self,
        session: Optional[aiohttp.ClientSession] = None,
        region: str = DEFAULT_REGION,
        token: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> None:
        """Initialize the client."""
        self._session = session
        self._close_session = False
        self._region = region
        self._base_url = API_HOSTS.get(region, API_HOSTS[DEFAULT_REGION])
        self._token = token
        self._user_id = user_id
        self._thing_models: Dict[str, Any] = load_cached_thing_models()
        self.last_stream_error: Optional[str] = None

    @property
    def token(self) -> Optional[str]:
        """Return the current auth token."""
        return self._token

    @property
    def user_id(self) -> Optional[str]:
        """Return the current user ID."""
        return self._user_id

    @property
    def thing_models(self) -> Dict[str, Any]:
        """Return cached thing models."""
        return self._thing_models

    def get_device_thing_model(self, dev: Dict[str, Any]) -> Dict[str, Any]:
        """Return thing model definition matching device model, productKey, or category."""
        if not self._thing_models:
            self._thing_models = load_cached_thing_models()

        candidates = [
            str(dev.get("model") or "").strip().lower(),
            str(dev.get("productKey") or "").strip().lower(),
            str(dev.get("deviceCategory") or "").strip().lower(),
            str(dev.get("model") or "").strip(),
            str(dev.get("productKey") or "").strip(),
        ]
        for c in candidates:
            if c and c in self._thing_models:
                return self._thing_models[c]

        for k, v in self._thing_models.items():
            for c in candidates:
                if c and k.lower() == c:
                    return v
        return {}

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            connector = aiohttp.TCPConnector(ssl=False)
            self._session = aiohttp.ClientSession(connector=connector)
            self._close_session = True
        return self._session

    async def close(self) -> None:
        """Close the underlying session if created internally."""
        if self._close_session and self._session and not self._session.closed:
            await self._session.close()

    async def _request_legacy(
        self,
        endpoint: str,
        params: Dict[str, Any],
        method: str = "POST",
    ) -> Dict[str, Any]:
        """Make a signed legacy request (used for auth and family/device list)."""
        session = await self._get_session()
        url = f"{self._base_url}{endpoint}"

        ts = str(int(time.time()))
        sign = param_sign(params, ts)

        payload = {
            "data": params,
            "timestamp": ts,
            "sign": sign,
        }

        headers = {
            "Content-Type": "application/json",
            "x-token": self._token or "",
            "x-lang": "zh_CN" if self._region == REGION_CN else "en_US",
        }

        try:
            async with session.request(
                method, url, json=payload, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                raw_bytes = await resp.read()
                text = raw_bytes.decode("utf-8", errors="replace")
                if resp.status == 401:
                    raise HomerunAuthError("Token expired or unauthorized (401)")
                if resp.status != 200:
                    raise HomerunConnectionError(f"HTTP error {resp.status}: {text}")

                try:
                    res_json = json.loads(text)
                except json.JSONDecodeError as err:
                    raise HomerunApiError(f"Invalid JSON response: {text}") from err

                code = str(res_json.get("code", ""))
                msg = res_json.get("msg", "")

                if code == "200":
                    return res_json.get("data", {})
                if code in ("4001", "401"):
                    raise HomerunAuthError(msg if msg else f"认证失败 ({code})")

                raise HomerunApiError(msg if msg else f"API错误 ({code})")

        except aiohttp.ClientError as err:
            raise HomerunConnectionError(f"Connection error requesting {url}: {err}") from err
        except asyncio.TimeoutError as err:
            raise HomerunConnectionError(f"Timeout requesting {url}") from err

    async def _request_v1_properties(
        self,
        endpoint: str,
        method: str = "GET",
        json_data: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Make a request to /v1/devices/.../properties."""
        session = await self._get_session()
        url = f"{self._base_url}{endpoint}"

        headers = {
            "Content-Type": "application/json",
            "Authorization": self._token or "",
            "x-token": self._token or "",
            "x-lang": "zh_CN" if self._region == REGION_CN else "en_US",
        }

        try:
            async with session.request(
                method, url, json=json_data, headers=headers, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                raw_bytes = await resp.read()
                text = raw_bytes.decode("utf-8", errors="replace")
                if resp.status == 401:
                    raise HomerunAuthError("Token expired (401)")
                if resp.status not in (200, 201):
                    raise HomerunConnectionError(f"HTTP error {resp.status}: {text}")

                try:
                    res_json = json.loads(text)
                except json.JSONDecodeError as err:
                    raise HomerunApiError(f"Invalid JSON response: {text}") from err

                # The v1 endpoints return either {"code": 200, "data": ...} or direct payload
                if isinstance(res_json, dict) and "code" in res_json:
                    code = str(res_json.get("code"))
                    if code not in ("200", "0"):
                        msg = res_json.get("msg", "")
                        raise HomerunApiError(msg if msg else f"API错误 ({code})")
                    return res_json.get("data", {})

                return res_json

        except aiohttp.ClientError as err:
            raise HomerunConnectionError(f"Connection error requesting {url}: {err}") from err
        except asyncio.TimeoutError as err:
            raise HomerunConnectionError(f"Timeout requesting {url}") from err

    async def async_login_phone(
        self,
        phone: str,
        password: str,
        area_code: str = "+86",
        country_code: str = "CN",
    ) -> Dict[str, Any]:
        """Log in with phone number and password."""
        hashed_pwd = hash_password(password)
        data = {
            "countryCode": country_code,
            "region": "Asia" if country_code == "CN" else "Overseas",
            "langType": "zh_CN" if country_code == "CN" else "en_US",
            "appId": APP_ID,
            "areaCode": area_code,
            "phone": phone,
            "password": hashed_pwd,
            "deviceId": hashlib.md5(f"ha_{phone}".encode()).hexdigest(),
            "model": "HomeAssistant",
        }
        res = await self._request_legacy("/app/v1/login/phonePassword", data)
        self._token = res.get("token")
        self._user_id = str(res.get("userId", ""))
        return res

    async def async_login_email(
        self,
        email: str,
        password: str,
        country_code: str = "CN",
    ) -> Dict[str, Any]:
        """Log in with email address and password."""
        hashed_pwd = hash_password(password)
        data = {
            "countryCode": country_code,
            "region": "Asia" if country_code == "CN" else "Overseas",
            "langType": "zh_CN" if country_code == "CN" else "en_US",
            "appId": APP_ID,
            "email": email,
            "password": hashed_pwd,
            "deviceId": hashlib.md5(f"ha_{email}".encode()).hexdigest(),
            "model": "HomeAssistant",
        }
        res = await self._request_legacy("/app/v1/login/emailPassword", data)
        self._token = res.get("token")
        self._user_id = str(res.get("userId", ""))
        return res

    async def async_get_families(self) -> List[Dict[str, Any]]:
        """Get the user's family / home list."""
        data = {
            "page": 1,
            "limit": 100,
        }
        res = await self._request_legacy("/app/v1/family/list", data)
        return res.get("list", []) if isinstance(res, dict) else []

    async def async_get_devices(self, family_id: int) -> List[Dict[str, Any]]:
        """Get device list for a given family."""
        data = {
            "familyId": family_id,
            "page": 1,
            "limit": 100,
        }
        res = await self._request_legacy("/app/v1/devices/list", data)
        return res.get("list", []) if isinstance(res, dict) else []

    async def async_get_ez_token(self) -> Dict[str, Any]:
        """Get Ezviz (萤石云) open video streaming token for camera devices."""
        try:
            res = await self._request_legacy("/app/v1/devices/ezToken", {})
            if not isinstance(res, dict):
                return {}
            token = res.get("accessToken")
            if token:
                # HomeRun returns this field AES encrypted. Its Android app decrypts
                # it before calling EZOpenSDK.setAccessToken().
                res = dict(res)
                res["accessToken"] = decrypt_ezviz_token(str(token))
            return res
        except Exception as err:
            self.last_stream_error = f"HomeRun ezToken 获取或解密失败: {err}"
            _LOGGER.warning("Could not fetch or decrypt Ezviz token: %s", err)
            return {}

    async def async_get_ezviz_live_url(
        self,
        camera_serial: str,
        token_data: Dict[str, Any],
        channel: int = 1,
        start_time: Optional[int] = None,
        stop_time: Optional[int] = None,
    ) -> Optional[str]:
        """Resolve a live or cloud-playback URL HA/go2rtc can ingest."""
        self.last_stream_error = None
        access_token = token_data.get("accessToken")
        domain = str(token_data.get("ysDomain") or "https://open.ys7.com")
        if not access_token:
            self.last_stream_error = "HomeRun ezToken 响应中没有 accessToken"
            return None
        if not camera_serial:
            self.last_stream_error = "设备详情中没有萤石摄像头序列号"
            return None

        parsed = urlsplit(domain if "://" in domain else f"https://{domain}")
        api_base = urlunsplit((parsed.scheme or "https", parsed.netloc, "", "", ""))
        url = f"{api_base.rstrip('/')}/api/lapp/v2/live/address/get"
        session = await self._get_session()

        is_playback = start_time is not None and stop_time is not None

        # Prefer HLS: the Ezviz HTTP-FLV endpoint may advertise H.264 initially
        # but later fail demuxing on some OEM cameras. HLS is stable in HA and
        # browser compatible. Keep FLV only as a fallback for older devices.
        for protocol in ((2,) if is_playback else (2, 4)):
            form = {
                "accessToken": str(access_token),
                "deviceSerial": camera_serial,
                "channelNo": str(channel),
                "protocol": str(protocol),
                "quality": "2",
                # This camera only exposes its real stream as HEVC.  Setting this
                # to 0 does not make Ezviz transcode it; Ezviz returns a short
                # H.264 ErrCode/9053 placeholder video instead.  Let go2rtc see
                # the real HEVC stream and transcode it for WebRTC clients.
                "supportH265": "1",
                "expireTime": "3600",
                "type": "3" if is_playback else "1",
            }
            if is_playback:
                form["startTime"] = datetime.fromtimestamp(start_time).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
                form["stopTime"] = datetime.fromtimestamp(stop_time).strftime(
                    "%Y-%m-%d %H:%M:%S"
                )
            try:
                async with session.post(
                    url,
                    data=form,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    payload = await resp.json(content_type=None)
                if str(payload.get("code")) == "200":
                    data = payload.get("data") or {}
                    if isinstance(data, dict) and data.get("url"):
                        return str(data["url"])
                    self.last_stream_error = (
                        f"萤石返回 200，但没有直播 URL（protocol={protocol}）"
                    )
                else:
                    self.last_stream_error = (
                        "萤石取流失败 "
                        f"code={payload.get('code')}, "
                        f"msg={payload.get('msg')}, protocol={protocol}"
                    )
                _LOGGER.warning(
                    "Ezviz live address failed for %s: %s",
                    camera_serial,
                    self.last_stream_error,
                )
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
                self.last_stream_error = (
                    f"请求萤石直播接口异常（protocol={protocol}）: {err}"
                )
                _LOGGER.warning(
                    "Could not resolve Ezviz stream for %s: %s",
                    camera_serial,
                    self.last_stream_error,
                )
        return None

    async def async_get_device_info(self, device_serial: str) -> Dict[str, Any]:
        """Fetch full device details, including a feeder's child camera list."""
        try:
            data = await self._request_legacy(
                "/app/v1/devices/info", {"deviceSerial": device_serial}
            )
            return data if isinstance(data, dict) else {}
        except Exception as err:
            _LOGGER.debug("Could not fetch device info for %s: %s", device_serial, err)
            return {}

    async def async_get_device_properties(self, device_serial: str) -> Dict[str, Any]:
        """Fetch current telemetry / property values for a device."""
        try:
            # 1. Try modern v1 REST property endpoint
            data = await self._request_v1_properties(f"/v1/devices/{device_serial}/properties", "GET")
            if isinstance(data, dict) and data:
                return data
        except Exception as err:
            _LOGGER.debug("v1 properties get not supported for %s (%s), querying OTAP properties", device_serial, err)

        # 2. Query basic info
        result_props: Dict[str, Any] = {}
        try:
            info_data = await self.async_get_device_info(device_serial)
            if isinstance(info_data, dict):
                result_props.update(info_data)
        except Exception as err:
            _LOGGER.debug("devices/info fallback failed for %s: %s", device_serial, err)

        # 3. Concurrently query real-time OTAP properties
        otap_queries = {
            "detect_presence_switch": ("CatDetect", "global", "customDomain"),
            "detect_behavior_switch": ("EatDetect", "global", "customDomain"),
            "object_frame_switch": ("BoundingBox", "global", "customDomain"),
            "camera_switch": ("VideoCtrl", "global", "customDomain"),
            "speaker_volume": ("Volume", "global", "customDomain"),
            "mic_switch": ("MicCtrl", "global", "customDomain"),
            "child_lock": ("KeyLockStatus", "global", "customDomain"),
            "feed_detect_switch": ("OutputSensorSwitch", "global", "customDomain"),
            "clog_detect_switch": ("BlockSensorSwitch", "global", "customDomain"),
            "night_mode": ("NightMode", "global", "customDomain"),
            "food_remain_status": ("LackFood", "global", "customDomain"),
            "desiccant_info": ("Desiccant", "global", "customDomain"),
            "next_feed_switch": ("CancelNextMeal", "PetFeederRes", "global"),
            "fan_speed": ("FanSpeed", "global", "customDomain"),
            "fan_switch": ("FanSwitch", "global", "customDomain"),
            "light_switch": ("LightSwitch", "global", "customDomain"),
            "auto_clean": ("AutoShovel", "global", "customDomain"),
            "auto_cover_switch": ("AutomaticBurial", "global", "customDomain"),
            "kitten_mode_switch": ("KittenProtection", "global", "customDomain"),
        }

        async def _fetch_one_otap(ha_prop: str, otap_prop: str, res_cat: str, dom_id: str):
            headers_dict = {
                "Content-Type": "application/json",
                "deviceSerial": device_serial,
                "localIndex": 0,
                "resourceCategory": res_cat,
                "domainIdentifier": dom_id,
                "propIdentifier": otap_prop,
            }
            payload = {
                "url": "/api/v3/device/otap/prop",
                "method": "GET",
                "headers": json.dumps(headers_dict),
                "body": json.dumps({}),
            }
            try:
                res = await self._request_legacy("/app/v1/devices/control", payload)
                val = res.get("data")
                if val is not None:
                    return ha_prop, val
            except Exception:
                pass
            return ha_prop, None

        tasks = [_fetch_one_otap(k, v[0], v[1], v[2]) for k, v in otap_queries.items()]
        otap_results = await asyncio.gather(*tasks)
        for ha_k, ha_v in otap_results:
            if ha_v is not None:
                result_props[ha_k] = ha_v

        return result_props

    async def async_set_device_properties(
        self, device_serial: str, properties: Dict[str, Any]
    ) -> bool:
        """Send property updates to device via OTAP control."""
        _LOGGER.debug("Setting properties for %s: %s", device_serial, properties)

        # OTAP Property Identifier and Category Mappings
        otap_map = {
            "detect_presence_switch": ("CatDetect", "global", "customDomain"),
            "detect_behavior_switch": ("EatDetect", "global", "customDomain"),
            "object_frame_switch": ("BoundingBox", "global", "customDomain"),
            "speaker_volume": ("Volume", "global", "customDomain"),
            "camera_switch": ("VideoCtrl", "global", "customDomain"),
            "mic_switch": ("MicCtrl", "global", "customDomain"),
            "child_lock": ("KeyLockStatus", "global", "customDomain"),
            "feed_detect_switch": ("OutputSensorSwitch", "global", "customDomain"),
            "clog_detect_switch": ("BlockSensorSwitch", "global", "customDomain"),
            "next_feed_switch": ("CancelNextMeal", "PetFeederRes", "global"),
            "night_mode": ("NightMode", "global", "customDomain"),
            "osd_time_switch": ("TimeWatermark", "global", "customDomain"),
            "desiccant_info": ("Desiccant", "global", "customDomain"),
            "light_switch": ("LightSwitch", "global", "customDomain"),
            "kitten_mode_switch": ("KittenProtection", "global", "customDomain"),
            "auto_cover_switch": ("AutomaticBurial", "global", "customDomain"),
            "auto_clean": ("AutoShovel", "global", "customDomain"),
        }

        success = True
        for prop_k, prop_v in properties.items():
            otap_prop, res_cat, dom_id = otap_map.get(prop_k, (prop_k, "global", "customDomain"))
            
            # Format body properly for OTAP
            if isinstance(prop_v, bool):
                body_str = "true" if prop_v else "false"
            elif isinstance(prop_v, (int, float)):
                body_str = str(int(prop_v))
            elif isinstance(prop_v, dict):
                body_str = json.dumps(prop_v)
            else:
                body_str = str(prop_v)

            headers_dict = {
                "Content-Type": "application/json",
                "deviceSerial": device_serial,
                "localIndex": 0,
                "resourceCategory": res_cat,
                "domainIdentifier": dom_id,
                "propIdentifier": otap_prop,
            }

            try:
                control_data = {
                    "url": "/api/v3/device/otap/prop",
                    "method": "PUT",
                    "headers": json.dumps(headers_dict),
                    "body": body_str,
                }
                await self._request_legacy("/app/v1/devices/control", control_data)
            except HomerunAuthError:
                raise
            except Exception as err:
                _LOGGER.error("Failed to control device %s prop %s (OTAP %s): %s", device_serial, prop_k, otap_prop, err)
                success = False

        return success

    async def async_invoke_service(
        self, device_serial: str, service_id: str, params: Optional[Dict[str, Any]] = None
    ) -> bool:
        """Invoke a device action service (e.g. remote_feed, remote_clean, filter_reset)."""
        _LOGGER.debug("Invoking service %s on %s with %s", service_id, device_serial, params)

        otap_actions = {
            "remote_feed": ("ManualFeed", "PetFeederRes", "global"),
            "announce_feed_voice": ("PlayFeedAudio", "global", "customDomain"),
            "desiccant_reset": ("Desiccant", "global", "customDomain"),
            "restart": ("RemoteReboot", "global", "customDomain"),
            "remote_clean": ("GeneralCmd", "global", "customDomain"),
            "remote_level": ("GeneralCmd", "global", "customDomain"),
            "temp_enable_camera": ("TempCamera", "global", "customDomain"),
        }

        act_ident, res_cat, dom_id = otap_actions.get(service_id, (service_id, "global", "customDomain"))

        # Format body value (e.g. portion count for ManualFeed)
        if service_id == "remote_feed":
            body_val = str(params.get("portion", 1)) if params else "1"
        elif service_id == "announce_feed_voice":
            body_val = "{}"
        elif service_id == "desiccant_reset":
            body_val = "1"
        else:
            body_val = json.dumps(params or {})

        headers_dict = {
            "Content-Type": "application/json",
            "deviceSerial": device_serial,
            "localIndex": 0,
            "resourceCategory": res_cat,
            "domainIdentifier": dom_id,
            "actionIdentifier": act_ident,
        }

        try:
            control_data = {
                "url": "/api/v3/device/otap/action",
                "method": "PUT",
                "headers": json.dumps(headers_dict),
                "body": body_val,
            }
            await self._request_legacy("/app/v1/devices/control", control_data)
            return True
        except HomerunAuthError:
            raise
        except Exception as err:
            _LOGGER.error("Service OTAP invocation failed for %s (%s): %s", service_id, act_ident, err)
            return False

    async def async_get_device_dynamics(
        self, device_serial: str, do_date: str, page: int = 1, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Fetch pet feeding and behavior dynamic records for a given date (YYYY-MM-DD)."""
        payload = {
            "deviceSerial": device_serial,
            "doDate": do_date,
            "page": page,
            "limit": limit,
        }
        try:
            res = await self._request_legacy("/app/v2/devicesDynamic/list", payload)
            if isinstance(res, dict) and "list" in res:
                return res["list"]
            if isinstance(res, list):
                return res
        except Exception as err:
            _LOGGER.debug("Failed to fetch dynamics for %s on %s: %s", device_serial, do_date, err)
        return []

    async def async_get_device_exceptions(
        self, device_serial: str
    ) -> List[Dict[str, Any]]:
        """Fetch the active device warnings shown by the official app."""
        res = await self._request_legacy(
            "/app/v1/devicesExceptionStatus/list",
            {"deviceSerial": device_serial},
        )
        if isinstance(res, dict) and isinstance(res.get("list"), list):
            return [item for item in res["list"] if isinstance(item, dict)]
        return []

    async def async_get_storage_download_url(self, storage_id: str) -> Optional[str]:
        """Fetch video / clip download URL from cloud storage ID."""
        if not storage_id:
            return None
        try:
            res = await self._request_legacy(
                "/app/v1/devicesCloudStorage/storageDownloadUrl", {"storageId": storage_id}
            )
            if isinstance(res, dict) and res.get("url"):
                return res["url"]
        except Exception as err:
            _LOGGER.debug("Failed to get storage download url for %s: %s", storage_id, err)
        return None
