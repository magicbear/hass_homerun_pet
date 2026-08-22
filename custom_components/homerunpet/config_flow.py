"""Config flow for Homerunpet (霍曼宠物) integration."""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession
import homeassistant.helpers.config_validation as cv

from .const import (
    ACCOUNT_TYPE_EMAIL,
    ACCOUNT_TYPE_PHONE,
    AREA_CODES,
    CONF_ACCOUNT_TYPE,
    CONF_AREA_CODE,
    CONF_FAMILY_ID,
    CONF_PASSWORD,
    CONF_REGION,
    CONF_SCAN_INTERVAL,
    CONF_TOKEN,
    CONF_USER_ID,
    CONF_USERNAME,
    DEFAULT_REGION,
    DEFAULT_SCAN_INTERVAL_SEC,
    DOMAIN,
    REGION_CN,
    REGION_EU,
    REGION_US,
)
from .homerun_api import (
    HomerunApiClient,
    HomerunApiError,
    HomerunAuthError,
    HomerunConnectionError,
    HomerunError,
    load_cached_thing_models,
)

_LOGGER = logging.getLogger(__name__)


class HomerunConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Homerunpet."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._account_type: str = ACCOUNT_TYPE_PHONE
        self._username: str = ""
        self._password: str = ""
        self._region: str = DEFAULT_REGION
        self._area_code: str = "+86"
        self._token: Optional[str] = None
        self._user_id: Optional[str] = None
        self._families: list[Dict[str, Any]] = []

    async def async_step_user(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: Dict[str, str] = {}
        description_placeholders: Dict[str, str] = {}

        if user_input is not None:
            self._account_type = user_input[CONF_ACCOUNT_TYPE]
            self._username = user_input[CONF_USERNAME].strip()
            self._password = user_input[CONF_PASSWORD].strip()
            self._region = user_input.get(CONF_REGION, DEFAULT_REGION)
            self._area_code = user_input.get(CONF_AREA_CODE, "+86")

            # Check if already configured
            unique_id = f"{self._account_type}_{self._username}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            await self.hass.async_add_executor_job(load_cached_thing_models)
            session = async_get_clientsession(self.hass)
            client = HomerunApiClient(session=session, region=self._region)
            try:
                if self._account_type == ACCOUNT_TYPE_EMAIL:
                    login_res = await client.async_login_email(
                        self._username, self._password, country_code=self._region
                    )
                else:
                    login_res = await client.async_login_phone(
                        self._username,
                        self._password,
                        area_code=self._area_code,
                        country_code=self._region,
                    )

                self._token = client.token
                self._user_id = client.user_id

                # Fetch families
                self._families = await client.async_get_families()

                if len(self._families) > 1:
                    return await self.async_step_family()

                family_id = self._families[0]["id"] if self._families else None
                family_name = self._families[0].get("name", "我的家") if self._families else "霍曼宠物"

                return self.async_create_entry(
                    title=f"霍曼宠物 ({self._username}) - {family_name}",
                    data={
                        CONF_ACCOUNT_TYPE: self._account_type,
                        CONF_USERNAME: self._username,
                        CONF_PASSWORD: self._password,
                        CONF_REGION: self._region,
                        CONF_AREA_CODE: self._area_code,
                        CONF_TOKEN: self._token,
                        CONF_USER_ID: self._user_id,
                        CONF_FAMILY_ID: family_id,
                    },
                )

            except HomerunAuthError as err:
                _LOGGER.warning("Homerun auth failed: %s", err)
                errors["base"] = "invalid_auth"
                description_placeholders["error_detail"] = str(err)
            except HomerunConnectionError as err:
                _LOGGER.warning("Homerun connection error: %s", err)
                errors["base"] = "cannot_connect"
                description_placeholders["error_detail"] = str(err)
            except HomerunError as err:
                _LOGGER.error("Homerun API error during login: %s", err)
                errors["base"] = "api_error"
                description_placeholders["error_detail"] = str(err)
            except Exception as err:
                _LOGGER.exception("Unexpected error during login: %s", err)
                errors["base"] = "unknown"
                description_placeholders["error_detail"] = str(err)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ACCOUNT_TYPE, default=ACCOUNT_TYPE_PHONE
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=ACCOUNT_TYPE_PHONE, label="手机号码 (Phone)"
                            ),
                            selector.SelectOptionDict(
                                value=ACCOUNT_TYPE_EMAIL, label="电子邮箱 (Email)"
                            ),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_REGION, default=REGION_CN
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=REGION_CN, label="中国大陆 (China Mainland)"
                            ),
                            selector.SelectOptionDict(
                                value=REGION_US, label="北美地区 (North America)"
                            ),
                            selector.SelectOptionDict(
                                value=REGION_EU, label="欧洲及其他 (Europe / Global)"
                            ),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_AREA_CODE, default="+86"
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=k, label=v)
                            for k, v in AREA_CODES.items()
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(CONF_USERNAME): str,
                vol.Required(CONF_PASSWORD): str,
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_family(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle family selection step if user has multiple families."""
        errors: Dict[str, str] = {}

        if user_input is not None:
            selected_family_id = int(user_input[CONF_FAMILY_ID])
            selected_family = next(
                (f for f in self._families if f.get("id") == selected_family_id), None
            )
            family_name = selected_family.get("name", "我的家") if selected_family else "霍曼家庭"

            return self.async_create_entry(
                title=f"霍曼宠物 ({self._username}) - {family_name}",
                data={
                    CONF_ACCOUNT_TYPE: self._account_type,
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_REGION: self._region,
                    CONF_AREA_CODE: self._area_code,
                    CONF_TOKEN: self._token,
                    CONF_USER_ID: self._user_id,
                    CONF_FAMILY_ID: selected_family_id,
                },
            )

        family_options = [
            selector.SelectOptionDict(
                value=str(f["id"]),
                label=f"{f.get('name', '未命名家庭')} ({'当前' if f.get('current') == 1 else '成员'})",
            )
            for f in self._families
        ]

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_FAMILY_ID,
                    default=str(self._families[0]["id"]) if self._families else "",
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=family_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="family",
            data_schema=schema,
            errors=errors,
        )

    async def async_step_reauth(
        self, entry_data: Dict[str, Any]
    ) -> FlowResult:
        """Handle re-authentication."""
        self._account_type = entry_data.get(CONF_ACCOUNT_TYPE, ACCOUNT_TYPE_PHONE)
        self._username = entry_data.get(CONF_USERNAME, "")
        self._region = entry_data.get(CONF_REGION, DEFAULT_REGION)
        self._area_code = entry_data.get(CONF_AREA_CODE, "+86")
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle re-auth confirmation."""
        errors: Dict[str, str] = {}
        description_placeholders: Dict[str, str] = {"username": self._username}

        if user_input is not None:
            password = user_input[CONF_PASSWORD].strip()
            session = async_get_clientsession(self.hass)
            client = HomerunApiClient(session=session, region=self._region)
            try:
                if self._account_type == ACCOUNT_TYPE_EMAIL:
                    await client.async_login_email(
                        self._username, password, country_code=self._region
                    )
                else:
                    await client.async_login_phone(
                        self._username,
                        password,
                        area_code=self._area_code,
                        country_code=self._region,
                    )

                existing_entry = await self.async_set_unique_id(
                    f"{self._account_type}_{self._username}"
                )
                if existing_entry:
                    self.hass.config_entries.async_update_entry(
                        existing_entry,
                        data={
                            **existing_entry.data,
                            CONF_PASSWORD: password,
                            CONF_TOKEN: client.token,
                            CONF_USER_ID: client.user_id,
                        },
                    )
                    await self.hass.config_entries.async_reload(existing_entry.entry_id)
                    return self.async_abort(reason="reauth_successful")

            except HomerunAuthError as err:
                errors["base"] = "invalid_auth"
                description_placeholders["error_detail"] = str(err)
            except HomerunConnectionError as err:
                errors["base"] = "cannot_connect"
                description_placeholders["error_detail"] = str(err)
            except HomerunError as err:
                errors["base"] = "api_error"
                description_placeholders["error_detail"] = str(err)
            except Exception as err:
                errors["base"] = "unknown"
                description_placeholders["error_detail"] = str(err)

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema({vol.Required(CONF_PASSWORD): str}),
            description_placeholders=description_placeholders,
            errors=errors,
        )

    async def async_step_reconfigure(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle reconfiguration of Homerunpet integration."""
        errors: Dict[str, str] = {}
        description_placeholders: Dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            account_type = user_input[CONF_ACCOUNT_TYPE]
            username = user_input[CONF_USERNAME].strip()
            password = user_input[CONF_PASSWORD].strip()
            region = user_input.get(CONF_REGION, DEFAULT_REGION)
            area_code = user_input.get(CONF_AREA_CODE, "+86")

            await self.hass.async_add_executor_job(load_cached_thing_models)
            session = async_get_clientsession(self.hass)
            client = HomerunApiClient(session=session, region=region)
            try:
                if account_type == ACCOUNT_TYPE_EMAIL:
                    login_res = await client.async_login_email(
                        username, password, country_code=region
                    )
                else:
                    login_res = await client.async_login_phone(
                        username,
                        password,
                        area_code=area_code,
                        country_code=region,
                    )

                self._account_type = account_type
                self._username = username
                self._password = password
                self._region = region
                self._area_code = area_code
                self._token = client.token
                self._user_id = client.user_id

                # Fetch families
                self._families = await client.async_get_families()

                if len(self._families) > 1:
                    return await self.async_step_reconfigure_family()

                family_id = self._families[0]["id"] if self._families else None
                family_name = self._families[0].get("name", "我的家") if self._families else "霍曼宠物"

                return self.async_update_reload_and_abort(
                    entry,
                    unique_id=f"{account_type}_{username}",
                    title=f"霍曼宠物 ({username}) - {family_name}",
                    data={
                        CONF_ACCOUNT_TYPE: account_type,
                        CONF_USERNAME: username,
                        CONF_PASSWORD: password,
                        CONF_REGION: region,
                        CONF_AREA_CODE: area_code,
                        CONF_TOKEN: client.token,
                        CONF_USER_ID: client.user_id,
                        CONF_FAMILY_ID: family_id,
                    },
                    reason="reconfigure_successful",
                )

            except HomerunAuthError as err:
                _LOGGER.warning("Homerun reconfigure auth failed: %s", err)
                errors["base"] = "invalid_auth"
                description_placeholders["error_detail"] = str(err)
            except HomerunConnectionError as err:
                _LOGGER.warning("Homerun reconfigure connection error: %s", err)
                errors["base"] = "cannot_connect"
                description_placeholders["error_detail"] = str(err)
            except HomerunError as err:
                _LOGGER.error("Homerun reconfigure API error: %s", err)
                errors["base"] = "api_error"
                description_placeholders["error_detail"] = str(err)
            except Exception as err:
                _LOGGER.exception("Unexpected error during reconfigure: %s", err)
                errors["base"] = "unknown"
                description_placeholders["error_detail"] = str(err)

        current_data = entry.data
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_ACCOUNT_TYPE,
                    default=current_data.get(CONF_ACCOUNT_TYPE, ACCOUNT_TYPE_PHONE),
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=ACCOUNT_TYPE_PHONE, label="手机号码 (Phone)"
                            ),
                            selector.SelectOptionDict(
                                value=ACCOUNT_TYPE_EMAIL, label="电子邮箱 (Email)"
                            ),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_REGION, default=current_data.get(CONF_REGION, REGION_CN)
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(
                                value=REGION_CN, label="中国大陆 (China Mainland)"
                            ),
                            selector.SelectOptionDict(
                                value=REGION_US, label="北美地区 (North America)"
                            ),
                            selector.SelectOptionDict(
                                value=REGION_EU, label="欧洲及其他 (Europe / Global)"
                            ),
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Optional(
                    CONF_AREA_CODE, default=current_data.get(CONF_AREA_CODE, "+86")
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=[
                            selector.SelectOptionDict(value=k, label=v)
                            for k, v in AREA_CODES.items()
                        ],
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                ),
                vol.Required(
                    CONF_USERNAME, default=current_data.get(CONF_USERNAME, "")
                ): str,
                vol.Required(
                    CONF_PASSWORD, default=current_data.get(CONF_PASSWORD, "")
                ): str,
            }
        )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=schema,
            errors=errors,
            description_placeholders=description_placeholders,
        )

    async def async_step_reconfigure_family(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Handle family selection during reconfiguration."""
        errors: Dict[str, str] = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            selected_family_id = int(user_input[CONF_FAMILY_ID])
            selected_family = next(
                (f for f in self._families if f.get("id") == selected_family_id), None
            )
            family_name = selected_family.get("name", "我的家") if selected_family else "霍曼家庭"

            return self.async_update_reload_and_abort(
                entry,
                unique_id=f"{self._account_type}_{self._username}",
                title=f"霍曼宠物 ({self._username}) - {family_name}",
                data={
                    CONF_ACCOUNT_TYPE: self._account_type,
                    CONF_USERNAME: self._username,
                    CONF_PASSWORD: self._password,
                    CONF_REGION: self._region,
                    CONF_AREA_CODE: self._area_code,
                    CONF_TOKEN: self._token,
                    CONF_USER_ID: self._user_id,
                    CONF_FAMILY_ID: selected_family_id,
                },
                reason="reconfigure_successful",
            )

        current_family_id = str(entry.data.get(CONF_FAMILY_ID, ""))
        family_options = [
            selector.SelectOptionDict(
                value=str(f["id"]),
                label=f"{f.get('name', '未命名家庭')} ({'当前' if f.get('current') == 1 else '成员'})",
            )
            for f in self._families
        ]

        default_fam = (
            current_family_id
            if any(str(f["id"]) == current_family_id for f in self._families)
            else (str(self._families[0]["id"]) if self._families else "")
        )

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_FAMILY_ID,
                    default=default_fam,
                ): selector.SelectSelector(
                    selector.SelectSelectorConfig(
                        options=family_options,
                        mode=selector.SelectSelectorMode.DROPDOWN,
                    )
                )
            }
        )

        return self.async_show_form(
            step_id="reconfigure_family",
            data_schema=schema,
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> HomerunOptionsFlowHandler:
        """Get the options flow for this handler."""
        return HomerunOptionsFlowHandler()


class HomerunOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for Homerunpet."""

    async def async_step_init(
        self, user_input: Optional[Dict[str, Any]] = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current_interval = self.config_entry.options.get(
            CONF_SCAN_INTERVAL,
            self.config_entry.data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SEC),
        )

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL, default=current_interval
                    ): vol.All(vol.Coerce(int), vol.Range(min=10, max=300)),
                }
            ),
        )
