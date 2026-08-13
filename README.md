# Home Assistant Facilioo

An unofficial Home Assistant custom integration for monthly consumption data from
[facilioo](https://www.facilioo.de/). It is intended for normal resident accounts and may also
work with white-label property-management apps whose accounts use the regular Facilioo backend.
It has been designed from the API behavior observed with the MÜNCH Immo App, but compatibility
with every Facilioo tenant or white-label app is not guaranteed.

This project is independent, community-maintained, and is not affiliated with or endorsed by
facilioo or MÜNCH.

## Features

- Warm-water consumption in m³
- Heating energy in kWh
- Latest monthly costs in Home Assistant's configured currency
- Cumulative total sensors with `state_class: total`
- Historical consumption and cost backfill through Home Assistant's supported Recorder
  statistics API
- Idempotent daily synchronization (one poll per day)
- Rewrites historical points when Facilioo corrects or deletes a reading
- Estimated-reading status on latest-month sensors
- German and English UI translations
- Config flow, reauthentication, diagnostics, and HACS-compatible layout
- No telemetry and no third-party data transfer

Facilioo provides billing/backend data with monthly resolution. This is not a live meter and the
integration deliberately does not poll every few minutes.

## Entities

Entities are created only when the corresponding source meter exists:

| Entity name | Meaning | Default |
| --- | --- | --- |
| Warm water total | Sum of all valid monthly warm-water readings | Enabled |
| Heating energy total | Sum of all valid monthly heating readings | Enabled |
| Warm water last month | Newest monthly value | Enabled |
| Heating energy last month | Newest monthly value | Enabled |
| Warm-water/heating cost last month | Newest monthly cost | Enabled |
| Warm-water/heating cost total | Sum of available costs | Disabled |

No cold-water entity is invented. Unknown meter types and units are ignored without preventing
supported meters from working.

## Installation

### HACS custom repository

1. Open HACS and select **Integrations**.
2. Open the menu and choose **Custom repositories**.
3. Add this GitHub repository URL with category **Integration**.
4. Install **Facilioo** and restart Home Assistant.

### Manual

Copy `custom_components/facilioo` into the `custom_components` directory of your Home Assistant
configuration, preserving the directory name, and restart Home Assistant.

## Setup

Go to:

**Settings → Devices & services → Add integration → Facilioo**

Enter the email address and password of the resident account. Setup performs a login and checks
that at least one supported meter is visible. Credentials are stored only in the Home Assistant
config entry. Access tokens exist only in memory, are never entities or diagnostics, and are
discarded on unload.

If Facilioo requires multi-factor authentication, setup stops with an explicit error. The
integration never asks the backend to skip MFA and currently cannot complete Facilioo's MFA
challenge because no resident-account challenge flow has been verified.

## Energy Dashboard and historical statistics

The **Warm water total** sensor is a valid Home Assistant water sensor (`device_class: water`,
`state_class: total`, `m³`) and can be selected under:

**Settings → Dashboards → Energy → Water consumption**

For correct pre-installation history, select the external statistic named **Facilioo warm water
consumption** when it is offered by the statistic picker. Heating history is published as
**Facilioo heating energy consumption** and is not automatically categorized as grid electricity.

When Facilioo supplies monthly costs, the integration also publishes **Facilioo warm water
costs** and **Facilioo heating costs** as independent cumulative external statistics in Home
Assistant's configured currency. The warm-water cost statistic can be selected as the cost
statistic for the corresponding water source in the Energy Dashboard. Missing cost fields do not
erase a previously imported amount; a newer reading explicitly marked as deleted does remove its
month from both cumulative histories.

### Why the backfill is an external statistic

Home Assistant 2026 uses two related Recorder paths: native sensors compile five-minute and
hourly statistics from state changes, while `async_add_external_statistics` imports authoritative
hourly statistics and safely updates a point with the same `(statistic_id, start)` key. The public
API does not provide a supported way for a custom integration to initialize the native sensor's
short-term sum baseline to an already accumulated historical total.

Importing old values under the native entity ID would therefore let the sensor compiler later
continue from a different zero point. This implementation does not rely on that unstable
combination. It exposes normal total entities for current Home Assistant state and a separate,
official external statistic for exact backfill. The total entities include a small
`historical_statistic_id` attribute to make this relationship inspectable. Consumption totals
also expose `historical_cost_statistic_id`, which points to the matching cost history.

Each historical series contains:

1. a zero baseline at the beginning of the first billing month;
2. one cumulative point at each following local month boundary;
3. aware UTC timestamps aligned to an exact hour, as Recorder requires.

For example, monthly values `0.172`, `0.766`, and `0.500 m³` produce sums `0`, `0.172`, `0.938`,
and `1.438`. A repeated sync submits the same keys and values, so Recorder updates rather than
duplicates them. If an old month changes or is deleted, the complete cumulative sequence is
recomputed and the affected boundaries are overwritten. No SQL, database-specific code, or
`.storage` manipulation is used.

## Time zones

`readingDate` must include an offset. Facilioo examples such as `2025-11-30T23:00:00Z` represent
the local German boundary at midnight. The integration converts the instant to Home Assistant's
configured time zone and looks one microsecond back from the interval end to identify the month
that ended. This also handles daylight-saving boundaries without fixed UTC-offset assumptions.

## Limitations

- Values are monthly, not real-time.
- Only data authorized for the configured Facilioo account can be imported.
- The currently verified meter metadata is type 5/M3 for warm water and type 4/KWH for heating;
  descriptive API labels are also used as a defensive fallback.
- There is no cold-water sensor unless a future, verified API source can be classified safely.
- White-label compatibility depends on the app using the regular Facilioo API and login.
- MFA challenges are detected but not yet supported.
- The API is external and may change. Unexpected records are skipped or surfaced as safe errors;
  the coordinator retains the last successful values when a refresh fails.
- The currency is taken from Home Assistant because the observed reading response provides costs
  but no reliable per-reading currency field.

## Privacy and security

Communication is limited to **Home Assistant ↔ `https://api.facilioo.de`**. There is no telemetry,
analytics, or forwarding of consumption data. Logs never intentionally include credentials,
tokens, full API payloads, or account email addresses. Diagnostics contain only counts, recognized
meter categories, update time, and API status.

See [SECURITY.md](SECURITY.md) before reporting a security issue. Never attach real credentials,
tokens, unredacted diagnostics, or personal meter identifiers to a public issue.

## Development

Python 3.13 or newer is required. With [uv](https://docs.astral.sh/uv/):

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

All HTTP tests use mocks. No productive Facilioo or Home Assistant system is contacted.

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidelines.

## License

MIT — see [LICENSE](LICENSE).
