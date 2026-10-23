# Facilioo API v2 — contract verification baseline

**Review date:** 2026-10-24  
**Tracking:** [Issue #58](https://github.com/dirrgang/home-assistant-facilioo/issues/58)

This is a **bounded, offline endpoint/request-contract baseline**, **not** a full
OpenAPI/schema conformance certification or proof that other white-label
accounts are compatible. No productive Facilioo account, user-specific data,
or resident token was used.

## Upstream sources and reproducibility

- [Official Developer Hub](https://developers.facilioo.de/)
- [Production OpenAPI v2 specification](https://api.facilioo.de/swagger/v2.0/swagger.json)
- [Authentication](https://developers.facilioo.de/reference/authentication)
- [Pagination](https://developers.facilioo.de/reference/pagination)
- Individual official endpoint pages are linked from
  [the reviewed contract fixture](../tests/fixtures/facilioo_api_v2_contract.json).

The documented endpoints, HTTP methods, login request fields, API version,
request pagination, and search filter names were checked against the public
reference pages on the review date. The upstream full Swagger JSON could
**not be fetched in the review environment**, so no claim is made about
matching every response DTO field, type, required property, nullability or
enum. The local fixture is a **human-reviewed subset of documented request
contracts**; it is not presented as a generated extract or immutable
snapshot of the upstream OpenAPI file.

To fetch the entire current official specification in a development
environment with network access (optional; **not** required by CI):

```sh
curl --fail --location --show-error \
  https://api.facilioo.de/swagger/v2.0/swagger.json \
  --output /tmp/facilioo-openapi-v2.json
python -m json.tool /tmp/facilioo-openapi-v2.json >/dev/null
```

Record the upstream version/retrieval date and compare **only the schemas
used by the integration** before expanding this verification baseline.
Review the diff manually; do not silently update expectations to follow an
incompatible upstream change. Do not commit the complete multi-megabyte
specification or enable network downloads in the normal unit-test CI.

## Reviewed HTTP and request contracts

| Endpoint | Method | Client usage | Source |
| --- | --- | --- | --- |
| `/api/auth/login` | POST | Email/password login, `skipMultiFactorAuthentication: false` | [Login](https://developers.facilioo.de/reference/post_api-auth-login) |
| `/api/accounts/myself` | GET | Account-ID fallback | [Get Myself](https://developers.facilioo.de/reference/get_api-accounts-myself) |
| `/api/consumption-meters` | GET | Paginated meter metadata | [List meters](https://developers.facilioo.de/reference/get_api-consumption-meters) |
| `/api/consumption-types` | GET | Paginated consumption type metadata | [List types](https://developers.facilioo.de/reference/get_api-consumption-types) |
| `/api/consumption-readings` | GET | Available in client; not main coordinator sync | [List readings](https://developers.facilioo.de/reference/get_api-consumption-readings) |
| `/api/consumption-readings-extended` | GET | Available in client; not main coordinator sync | [Extended readings](https://developers.facilioo.de/reference/get_api-consumption-readings-extended) |
| `/api/consumption-readings/search` | POST | Main sync; `orderBy`, optional `changedSince` and `dates` | [Search readings](https://developers.facilioo.de/reference/post_api-consumption-readings-search) |

The official pagination guide documents 1-based `PageNumber`, maximum
`PageSize = 100`, and the response fields `items`, `totalCount`,
`totalPages` and `hasNextPage`. GET and POST search requests place
pagination parameters in the **query string**. The integration sends
`api-version: 2.0` and uses JWT bearer authentication outside login.
The search guide describes `changedSince` as matching creations **or**
modifications since the supplied timestamp; `dates` accepts `YYYY-MM`
(and optionally a complete year).

The login reference currently marks `skipMultiFactorAuthentication`
**deprecated but required**; the integration must continue to send
`false` unless a reviewed contract change justifies another behavior.
MFA challenge handling and its dedicated regression tests remain in
[Issue #49](https://github.com/dirrgang/home-assistant-facilioo/issues/49).

## Automated baseline

[Offline contract tests](../tests/test_api_contract.py) use a synthetic
in-memory HTTP session and the small reviewed JSON fixture. They guard:
- Documented HTTP methods, endpoint paths and the `api-version` header.
- Login body fields, **no MFA bypass**, no bearer header on login, and
  bearer authorization on subsequent requests.
- 1-based paging, page size 100, and multi-page `hasNextPage` handling.
- POST search filter names, the documented `YYYY-MM` date format,
  and timezone-aware conversion of `changedSince` to UTC.

Run locally:

```sh
uv run pytest tests/test_api_contract.py
uv run ruff check tests/test_api_contract.py
```

These tests are **not** live contract probes: they cannot establish whether
Facilioo changed the production API after the source review date.

## Open work in Issue #58

The following remain **unverified against the full OpenAPI v2 schema**:
- Required/nullable and typed fields for `ConsumptionMeterRead`,
  `ConsumptionTypeRead`, `ConsumptionReadingRead`, and the extended
  reading variant.
- Login/AccountRead response DTOs, optional account identity shapes,
  and response error-schema details.
- Whether nullable `currentValue`, monetary `costs`, alternative-unit
  readings, `deleted`, and `lastModified` have exactly the parser-assumed
  types and formats in the current upstream specification.

The integration already has independent mock-based model tests for several
of these behaviors; they are not evidence of a verified upstream schema.
Expand the contract tests only after checking the actual upstream
definitions and capturing a **minimal synthetic fixture** for each proven
variation. Raise separate defects only for demonstrated functional problems.
