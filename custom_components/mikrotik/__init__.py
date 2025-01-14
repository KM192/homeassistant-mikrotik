import asyncio
import logging

import voluptuous as vol
import re

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_HOST, CONF_USERNAME, CONF_PASSWORD,
                                 CONF_PORT, CONF_NAME, CONF_COMMAND)

from librouteros import connect
from librouteros.query import Key

from .const import (DEFAUL_PORT, RUN_SCRIPT_COMMAND, REMOVE_COMMAND,
                    ADD_COMMAND, UPDATE_COMMAND, API_COMMAND, CONF_COMMAND,
                    CONF_PARAMS, CONF_FIND, CONF_FIND_PARAMS)

__version__ = '1.2.0'

REQUIREMENTS = ['librouteros==3.0.0']

DOMAIN = "mikrotik"

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN:
        vol.Schema({
            vol.Required(CONF_HOST): cv.string,
            vol.Required(CONF_USERNAME): cv.string,
            vol.Optional(CONF_PASSWORD): cv.string,
            vol.Optional(CONF_PORT): cv.port
        }),
    },
    extra=vol.ALLOW_EXTRA)

SCRIPT_SCHEMA = vol.Schema({
    vol.Required(CONF_NAME): cv.string
})

ADD_SCHEMA = vol.Schema({
    vol.Required(CONF_COMMAND): cv.string,
    vol.Required(CONF_PARAMS): cv.string
})

COMMAND_SCHEMA = vol.Schema({
    vol.Required(CONF_COMMAND): cv.string,
    vol.Optional(CONF_PARAMS): cv.string,
    vol.Optional(CONF_FIND): cv.string,
    vol.Optional(CONF_FIND_PARAMS): cv.string
})


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize of Mikrotik component."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD, "")
    port = conf.get(CONF_PORT, DEFAUL_PORT)

    def get_api():
        try:
            api = connect(
                host=host, username=username, password=password, port=port)
            _LOGGER.info("Connected to %s:%u", host, port)
            return api

        except (librouteros.exceptions.TrapError,
                librouteros.exceptions.MultiTrapError,
                librouteros.exceptions.ConnectionError) as api_error:
            _LOGGER.error("Connection error: %s", str(api_error))

    def get_params(params):
        ret = []

        # convert params to dictionary
        if params and len(params) > 0:
            ret = dict(re.findall(r'([^\s]+)=(?:"|\')([^"]+)(?:"|\')', params))

        return ret

    def get_ids(api, call):
        find = call.data.get(CONF_FIND)
        find_params = call.data.get(CONF_FIND_PARAMS)
        ids = []

        if find and find_params:
            find = find.split(' ')
            # convert find_params to dictionary, keep type
            required_params = re.findall(
                r'([^\s]+)(?:=|~)(?:"|\')([^"]+)(?:"|\')', find_params)

            _LOGGER.info("Find cmd: %s", find)
            _LOGGER.info("Required params: %s", required_params)

            # exlude find and cmd
            for item in api.path(*find):
                param_counter = 0

                for param in required_params:
                    if param[0] in item:
                        if re.search(param[1], item.get(param[0])):
                            param_counter += 1

                        if len(required_params) == param_counter:
                            _LOGGER.debug("Found item: %s", item)
                            ids.append(item.get('.id'))

            if len(ids) > 0:
                return ids

        _LOGGER.warning("Required params not found")
        return []

    async def run_script(call):
        api = get_api()

        if CONF_NAME in call.data:
            req_script = call.data.get(CONF_NAME)

            _LOGGER.debug("Sending request to run '%s' script", req_script)

            try:
                name = Key('name')
                id = Key('.id')

                for script_id in api.path(
                        'system',
                        'script').select(id).where(name == req_script):
                    _LOGGER.info("Running script: %s", script_id)

                    cmd = api.path('system', 'script')
                    tuple(cmd('run', **script_id))

            except Exception as e:
                _LOGGER.error("Run script error: %s", str(e))

    async def remove(call):
        command = call.data.get(CONF_COMMAND).split(' ')

        api = get_api()

        try:
            params = get_params(call.data.get(CONF_PARAMS))
            ids = get_ids(api, call)

            if len(ids) > 0 and len(params) > 0:
                _LOGGER.error("Use only params or find_params not both")
                return
            elif len(ids) == 0 and (len(params) == 0 or '.id' not in params):
                _LOGGER.error("Missing ID")
                return

            _LOGGER.debug("REMOVE command id: %s %s",
                          list(params.values()) if len(params) else ids)

            params = list(params.values()) if len(params) > 0 else ids
            cmd = api.path(*command)
            cmd.remove(*params)

        except Exception as e:
            _LOGGER.error("Remove API error: %s", str(e))

    async def add(call):
        command = call.data.get(CONF_COMMAND).split(' ')

        api = get_api()

        try:
            params = get_params(call.data.get(CONF_PARAMS))

            if len(params) == 0:
                _LOGGER.error("Missing parameters")
                return

            _LOGGER.debug("ADD command params: %s", params)

            cmd = api.path(*command)
            _LOGGER.info("Returned id: %s", cmd.add(**params))

        except Exception as e:
            _LOGGER.error("Add API error: %s", str(e))

    async def update(call):
        command = call.data.get(CONF_COMMAND).split(' ')

        api = get_api()

        try:
            params = get_params(call.data.get(CONF_PARAMS))
            ids = get_ids(api, call)

            for i in range(max(len(ids), bool(len(params)))):
                if len(ids) > 0:
                    if params:
                        params = {**params, **{'.id': ids[i]}}
                    else:
                        params = ids[i]
                elif '.id' not in params:
                    _LOGGER.error("Missing ID")
                    return

                _LOGGER.info("Update parameters: %s", params)
                cmd = api.path(*command)
                cmd.update(**params)

        except Exception as e:
            _LOGGER.error("Update API error: %s", str(e))

    async def command(call):
        command = call.data.get(CONF_COMMAND).split(' ')

        api = get_api()

        try:
            params = get_params(call.data.get(CONF_PARAMS))
            ids = get_ids(api, call)

            if len(ids) > 0 or len(params) > 0:
                for i in range(max(len(ids), bool(len(params)))):
                    if len(ids) > 0:
                        if params:
                            params = {**params, **{'.id': ids[i]}}
                        else:
                            params = {'.id': ids[i]}

                    _LOGGER.info("Query parameters: %s", params)
                    cmd = api.path(*command[:-1])
                    tuple(cmd(command[-1], **params))

            else:
                _LOGGER.info("Result: %s", list(api.path(*command)))

        except Exception as e:
            _LOGGER.error("API error: %s", str(e))

    hass.services.async_register(
        DOMAIN, RUN_SCRIPT_COMMAND, run_script, schema=SCRIPT_SCHEMA)
    hass.services.async_register(
        DOMAIN, REMOVE_COMMAND, remove, schema=COMMAND_SCHEMA)
    hass.services.async_register(
        DOMAIN, ADD_COMMAND, add, schema=ADD_SCHEMA)
    hass.services.async_register(
        DOMAIN, UPDATE_COMMAND, update, schema=COMMAND_SCHEMA)
    hass.services.async_register(
        DOMAIN, API_COMMAND, command, schema=COMMAND_SCHEMA)

    return True
