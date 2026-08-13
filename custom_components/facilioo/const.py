"""Constants for the Facilioo integration."""

from datetime import timedelta

DOMAIN = "facilioo"
NAME = "Facilioo"
VERSION = "0.1.5"

BASE_URL = "https://api.facilioo.de"
API_VERSION = "2.0"
LOGIN_ENDPOINT = "/api/auth/login"
METERS_ENDPOINT = "/api/consumption-meters"
READINGS_ENDPOINT = "/api/consumption-readings"
EXTENDED_READINGS_ENDPOINT = "/api/consumption-readings-extended"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
PLATFORMS = ["sensor"]
UPDATE_INTERVAL = timedelta(days=1)
REQUEST_TIMEOUT = 30
PAGE_SIZE = 100

TYPE_HEATING = 4
TYPE_WARM_WATER = 5
UNIT_KWH = "KWH"
UNIT_M3 = "M3"

STATISTIC_WARM_WATER = "warm_water_consumption"
STATISTIC_HEATING = "heating_energy_consumption"
STATISTIC_WARM_WATER_COSTS = "warm_water_costs"
STATISTIC_HEATING_COSTS = "heating_costs"
STORE_VERSION = 1
