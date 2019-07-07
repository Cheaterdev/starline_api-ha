import logging
import re
import json
import subprocess
from collections import namedtuple
from datetime import timedelta
import time

import hashlib
import voluptuous as vol
import requests
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
from homeassistant.components.device_tracker import PLATFORM_SCHEMA
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_SCAN_INTERVAL

from homeassistant.util import Throttle
from requests_toolbelt.utils import dump
_LOGGER = logging.getLogger(__name__)
from homeassistant.helpers.event import async_track_time_interval

CONF_APP_ID = 'app_id'
CONF_APP_SECRET = 'app_secret'
DEFAULT_INTERVAL = timedelta(minutes=2)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Required(CONF_APP_ID): cv.string,
    vol.Required(CONF_APP_SECRET): cv.string,
    vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_INTERVAL):
            vol.All(cv.time_period, cv.positive_timedelta),
})

def setup_scanner(hass, config: dict, see, discovery_info=None):
    StarlineAPIScanner(hass, config, see)
    return True

class StarlineAPIScanner(object):

    exclude = []
    def __init__(self, hass, config: dict, see):
        self.see = see
        self.hass = hass

        self.app_id = config.get(CONF_APP_ID)
        self.app_secret = config.get(CONF_APP_SECRET)

        self.user_name = config.get(CONF_USERNAME)
        self.user_pass = config.get(CONF_PASSWORD)

        while True:
            self.session = requests.Session() 
            try:
                self.app_code = self.get_app_code(self.app_id, self.app_secret)
                self.app_token = self.get_app_token(self.app_id, self.app_secret, self.app_code)
                self.user_slid = self.get_slid_user_token(self.app_token, self.user_name, self.user_pass)
                self.user_id = self.get_user_id(self.user_slid)       
                break
            except Exception as e:
                _LOGGER.error("error: "  + str(e))
                time.sleep(5)
                break
        #track_utc_time_change(self.hass, self._update_info, minute=range(0, 60, 2))
        self._update_info()
        async_track_time_interval(self.hass, self._update_info, config.get(CONF_SCAN_INTERVAL))
       
    def get_app_code(self, app_id, app_secret):
        """
        Получение кода приложения для дальнейшего получения токена.
        Идентификатор приложения и пароль выдаются контактным лицом СтарЛайн.
        :param app_id: Идентификатор приложения
        :param app_secret: Пароль приложения
        :return: Код, необходимый для получения токена приложения
        """
        url = 'https://id.starline.ru/apiV3/application/getCode/'
        _LOGGER.debug('execute request: {}'.format(url))

        payload = {
            'appId': app_id,
            'secret': hashlib.md5(app_secret.encode('utf-8')).hexdigest()
        }

        r = self.session.get(url, params=payload)
        response = r.json()
        _LOGGER.debug('payload : {}'.format(payload))
        _LOGGER.debug('response info: {}'.format(r))
        _LOGGER.debug('response data: {}'.format(response))
        if int(response['state']) == 1:
            app_code = response['desc']['code']
            _LOGGER.debug('Application code: {}'.format(app_code))
            return app_code
        raise Exception(response)

    def get_app_token(self, app_id, app_secret, app_code):
        """
        Получение токена приложения для дальнейшей авторизации.
        Время жизни токена приложения - 4 часа.
        Идентификатор приложения и пароль можно получить на my.starline.ru.
        :param app_id: Идентификатор приложения
        :param app_secret: Пароль приложения
        :param app_code: Код приложения
        :return: Токен приложения
        """
        url = 'https://id.starline.ru/apiV3/application/getToken/'
        _LOGGER.debug('execute request: {}'.format(url))
        payload = {
            'appId': app_id,
            'secret': hashlib.md5((app_secret + app_code).encode('utf-8')).hexdigest()
        }
        r = self.session.get(url, params=payload)
        response = r.json()
        _LOGGER.debug('payload: {}'.format(payload))
        _LOGGER.debug('response info: {}'.format(r))
        _LOGGER.debug('response data: {}'.format(response))
        if int(response['state']) == 1:
            app_token = response['desc']['token']
            _LOGGER.debug('Application token: {}'.format(app_token))
            return app_token
        raise Exception(response)

    def get_slid_user_token(self, app_token, user_login, user_password):
        """
        Аутентификация пользователя по логину и паролю.
        Неверные данные авторизации или слишком частое выполнение запроса авторизации с одного
        ip-адреса может привести к запросу капчи.
        Для того, чтобы сервер SLID корректно обрабатывал клиентский IP,
        необходимо проксировать его в параметре user_ip.
        В противном случае все запросы авторизации будут фиксироваться для IP-адреса сервера приложения, что приведет к частому требованию капчи.
        :param sid_url: URL StarLineID сервера
        :param app_token: Токен приложения
        :param user_login: Логин пользователя
        :param user_password: Пароль пользователя
        :return: Токен, необходимый для работы с данными пользователя. Данный токен потребуется для авторизации на StarLine API сервере.
        """
        url = 'https://id.starline.ru/apiV3/user/login/'
        _LOGGER.debug('execute request: {}'.format(url))
        payload = {
            'token': app_token
        }
        data = {}
        data["login"] = user_login
        data["pass"] = hashlib.sha1(user_password.encode('utf-8')).hexdigest()
        r = self.session.post(url, params=payload, data=data)
        response = r.json()
        _LOGGER.debug('payload : {}'.format(payload))
        _LOGGER.debug('response info: {}'.format(r))
        _LOGGER.debug('response data: {}'.format(response))
        if int(response['state']) == 1:
            slid_token = response['desc']['user_token']
            _LOGGER.debug('SLID token: {}'.format(slid_token))
            return slid_token
        raise Exception(response)

    def get_user_id(self, slid_token):
        """
        Авторизация пользователя по токену StarLineID. Токен авторизации предварительно необходимо получить на сервере StarLineID.
        :param slid_token: Токен StarLineID
        :return: Токен пользователя на StarLineAPI
        """
        url = 'https://developer.starline.ru/json/v2/auth.slid'
        _LOGGER.debug('execute request: {}'.format(url))
        data = {
            'slid_token': slid_token
        }
        r = self.session.post(url, json=data)
        response = r.json()
        _LOGGER.debug('response info: {}'.format(r))
        _LOGGER.debug('response data: {}'.format(response))
        slnet_token = r.cookies["slnet"]
        _LOGGER.debug('slnet token: {}'.format(slnet_token))
        return response['user_id']

    def get_devices(self, user_id):
        url = 'https://developer.starline.ru/json/v1/user/' + str(user_id) + '/user_info/'
        _LOGGER.debug('execute request: {}'.format(url))

        r = self.session.get(url)
        response = r.json()
        _LOGGER.debug('response info: {}'.format(r))
        _LOGGER.debug('response data: {}'.format(response))
        if int(response['code']) == 200:
            devices = response['devices']
            #_LOGGER.debug('Application token: {}'.format(app_token))
            return devices
        raise Exception(response)

    def _update_info(self, now=None):
        
        devices = self.get_devices(self.user_id)

        for device in devices:
            x = device['position']['x']
            y = device['position']['y']

            dev_id = device['device_id']

            attrs = { }
            
            if 'ctemp' in device:
                attrs.update({'climate_temp': device['ctemp']})

            if 'etemp' in device:
                attrs.update({'engine_temp': device['etemp']})

            if 'battery' in device:
                attrs.update({'battery': device['battery']})

            if 'balance' in device:
                attrs.update({'balance': device['balance']})

            if 'car_state' in device:
                states = device['car_state']
                _LOGGER.debug("Found states: "  + json.dumps(states))
                if states:
                    attrs.update({ ("state_"+k): v for k, v in states.items() })
            
            if 'car_alr_state' in device:
                alarm_states = device['car_alr_state']
                _LOGGER.debug("Found alarm states: "  + json.dumps(states))
                if alarm_states:
                    attrs.update({ ("alarm_state_"+k): v for k, v in alarm_states.items() })
           
            self.see(dev_id="starline_" + str(dev_id), gps=(x, y), attributes=attrs)

        return True