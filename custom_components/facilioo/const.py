"""Constants for the Facilioo integration."""

from datetime import timedelta

DOMAIN = "facilioo"
NAME = "Facilioo"
VERSION = "0.2.0"

BASE_URL = "https://api.facilioo.de"
API_VERSION = "2.0"
LOGIN_ENDPOINT = "/api/auth/login"
METERS_ENDPOINT = "/api/consumption-meters"
READINGS_ENDPOINT = "/api/consumption-readings"
READINGS_SEARCH_ENDPOINT = "/api/consumption-readings/search"
EXTENDED_READINGS_ENDPOINT = "/api/consumption-readings-extended"

CONF_EMAIL = "email"
CONF_PASSWORD = "password"
PLATFORMS = ["sensor"]
UPDATE_INTERVAL = timedelta(days=1)
SYNC_OVERLAP = timedelta(minutes=5)
RECONCILIATION_INTERVAL = timedelta(days=7)
REQUEST_TIMEOUT = 30
PAGE_SIZE = 100

TYPE_HEATING = 4
TYPE_WARM_WATER = 5
UNIT_KWH = "KWH"
UNIT_M3 = "M3"

STATISTIC_WARM_WATER = "warm_water_consumption"
STATISTIC_WARM_WATER_ENERGY = "warm_water_energy_consumption"
STATISTIC_HEATING = "heating_energy_consumption"
STATISTIC_WARM_WATER_COSTS = "warm_water_costs"
STATISTIC_HEATING_COSTS = "heating_costs"
STORE_VERSION = 1
SYNC_STORE_VERSION = 1
