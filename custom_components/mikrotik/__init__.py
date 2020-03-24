import asyncio
import logging

import voluptuous as vol
import re

import homeassistant.helpers.config_validation as cv
from homeassistant.const import (CONF_HOST, CONF_USERNAME, CONF_PASSWORD,
                                 CONF_PORT, CONF_NAME, CONF_COMMAND)

from librouteros import connect
from librouteros.query import Key

from .const import (DEFAUL_PORT, RUN_SCRIPT_COMMAND, API_COMMAND, CONF_FIND,
                    CONF_FIND_PARAMS, CONF_ADD, CONF_REMOVE, CONF_UPDATE,
                    CONF_PARAMS)

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

SCRIPT_SCHEMA = vol.Schema({vol.Required(CONF_NAME): cv.string})

API_SCHEMA = vol.Schema({
    vol.Required(CONF_COMMAND): cv.string,
    vol.Optional(CONF_FIND): cv.string,
    vol.Optional(CONF_FIND_PARAMS): cv.string,
    vol.Optional(CONF_ADD): cv.string,
    vol.Optional(CONF_REMOVE): cv.string,
    vol.Optional(CONF_UPDATE): cv.string,
    vol.Optional(CONF_PARAMS): cv.string
})


@asyncio.coroutine
def async_setup(hass, config):
    """Initialize of Mikrotik component."""
    conf = config[DOMAIN]
    host = conf.get(CONF_HOST)
    username = conf.get(CONF_USERNAME)
    password = conf.get(CONF_PASSWORD, "")
    port = conf.get(CONF_PORT, DEFAUL_PORT)

    _LOGGER.info("Setup")

    @asyncio.coroutine
    def run(call):
        """Run script service."""

        try:
            api = connect(
                host=host, username=username, password=password, port=port)

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

            elif CONF_COMMAND in call.data:
                try:
                    command = call.data.get(CONF_COMMAND).split(' ')
                    find = call.data.get(CONF_FIND)
                    find_params = call.data.get(CONF_FIND_PARAMS)
                    add = call.data.get(CONF_ADD)
                    remove = call.data.get(CONF_REMOVE)
                    update = call.data.get(CONF_UPDATE)
                    params = call.data.get(CONF_PARAMS)

                    if len(command) < 2:
                        _LOGGER.error(
                            "Invalid command, must include at least 2 words")
                        return

                    _LOGGER.info("API request: %s", command)
                    ids = []

                    if find and find_params:
                        find = find.split(' ')
                        # convert find_params to dictionary, keep type
                        required_params = re.findall(
                            r'([^\s]+)(=|~)(?:"|\')([^"]+)(?:"|\')',
                            find_params)

                        _LOGGER.info("Find cmd: %s", find)
                        _LOGGER.info("Required params: %s", required_params)

                        # exlude find and cmd
                        for item in api.path(*find):
                            param_counter = 0

                            for param in required_params:
                                if param[0] in item:
                                    if param[1] == '~' and re.search(
                                            param[2], item.get(param[0])):
                                        param_counter += 1

                                    elif param[1] == '=' and item.get(
                                            param[0]) == param[2]:
                                        param_counter += 1

                                    if len(required_params) == param_counter:
                                        _LOGGER.debug("Found item: %s", item)
                                        ids.append({'.id': item.get('.id')})

                        if len(ids) == 0:
                            _LOGGER.warning("Required params not found")
                            return

                    # convert params to dictionary
                    if params and len(params) > 0:
                        params = dict(
                            re.findall(r'([^\s]+)=(?:"|\')([^"]+)(?:"|\')',
                                       params))
                        _LOGGER.info("Params: %s", params)

                    if (add or remove or update):
                        if len(params) == 0:
                            _LOGGER.error("Missing parameters")
                            return

                        # cmd = api.path(*command)

                        if add:
                            _LOGGER.error("ADD command is TODO")
                            # cmd.add(**params)

                        elif remove:
                            _LOGGER.error("REMOVE command is TODO")
                            # cmd.remove(**params)

                        elif update:
                            _LOGGER.error("UPDATE command is TODO")
                            # cmd.update(**params)

                    else:
                        if len(ids) > 0:
                            for id in ids:
                                if params:
                                    params = {**params, **id}

                                else:
                                    params = id

                                cmd = api.path(*command[:-1])
                                tuple(cmd(command[-1], **params))

                        elif len(params) > 0:
                            cmd = api.path(*command[:-1])
                            tuple(cmd(command[-1], **params))

                        else:
                            _LOGGER.info("Result: %s", list(
                                api.path(*command)))

                except Exception as e:
                    _LOGGER.error("API error: %s", str(e))

        except (librouteros.exceptions.TrapError,
                librouteros.exceptions.MultiTrapError,
                librouteros.exceptions.ConnectionError) as api_error:
            _LOGGER.error("Connection error: %s", str(api_error))

    hass.services.async_register(
        DOMAIN, RUN_SCRIPT_COMMAND, run, schema=SCRIPT_SCHEMA)

    hass.services.async_register(DOMAIN, API_COMMAND, run, schema=API_SCHEMA)

    return True
