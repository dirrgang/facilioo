# Publicly documented Facilioo property-management portals

**Last source review:** 2026-10-23

This is a **non-exhaustive, source-backed list** of property managers that have
publicly identified Facilioo as a customer portal, branded app, or service
provider. It helps residents recognize a possible Facilioo-backed portal and
helps contributors prioritize further compatibility investigations.

**This is not a list of supported integrations or tested accounts.**
A public reference to Facilioo does **not** establish that a particular
resident account can authenticate against the regular Facilioo API, exposes
heating or hot-water meter readings, or is compatible with
`home-assistant-facilioo`. White-label implementations can differ,
and multi-factor authentication is currently unsupported.

The integration's known working environment is described in the
[README](../README.md#installation): the regular Facilioo API as observed
through the MÜNCH Immo App. No other provider listed below has been
independently tested with this integration.

## Evidence categories

- **Customer portal/app:** The property manager's own website identifies a
  Facilioo customer-facing portal or app.
- **Service disclosure:** The manager's privacy notice names Facilioo as a
  service provider for customer data or portal access. This is not
  necessarily evidence of a particular app, login method, or meter API.
- **Historical reference:** An older published account of Facilioo adoption;
  continued use is **not confirmed**.

**Integration compatibility** is **unverified** for every organization in the
tables below. The status is deliberately not inferred from branding, login
screens, portal URLs, or Facilioo's public features.

## Publicly documented portals and services

| Property manager | Publicly described portal / relationship | Evidence | Source | Checked |
| --- | --- | --- | --- | --- |
| Clevesta GmbH | Facilioo customer/owner portal; privacy notice also mentions a separate Impower portal | Customer portal + service disclosure | [Privacy notice](https://clevesta.de/legal/datenschutz) | 2026-10-23 |
| Cornely & Roth GmbH | Facilioo customer portal/app; another service portal is also offered | Customer portal/app | [Customer login](https://www.cornely-roth.de/kundenlogin) | 2026-10-23 |
| GfH – Gesellschaft für Hausverwaltung mbH (Saarbrücken-Dudweiler) | “Zuhause – effizient verwaltet” customer app and Facilioo portal | Customer portal/app | [Customer portal](https://gfhdudweiler.de/kundenportal/) | 2026-10-23 |
| Haustakt GmbH | Facilioo customer portal available by web browser or app | Customer portal/app | [Customer portal](https://www.haustakt.com/kundenportal) | 2026-10-23 |
| Immo-Agentur MGL GmbH | Facilioo property portal for selected customers | Customer portal | [Property management](https://www.immo-mgl.de/verwaltung) | 2026-10-23 |
| Kassenbrock Hausverwaltung | “Kassenbrock HV App powered by facilioo” and customer portal | Branded customer app | [App information](https://www.kassenbrock.de/unsere-app/) | 2026-10-23 |
| KREMER Hausverwaltungen GmbH | Facilioo online portal/app used for customer-data administration | Service disclosure | [Customer privacy notice](https://www.kremerhv.de/datenschutzhinweise) | 2026-10-23 |
| MoVida | “MoVida Mieterportal” provided through a Facilioo platform | Customer portal + service disclosure | [Privacy notice](https://movidaliving.de/datenschutzerklaerung/) | 2026-10-23 |
| RS Hausverwaltung | Facilioo customer portal; the website also describes a planned transition to Facilioo Neo | Customer portal/app | [Customer portal](https://www.rshv.de/kundenportal/) | 2026-10-23 |
| Strauß & Bock Immobilien | Facilioo customer portal for owners, tenants, and contractors | Customer portal/app | [Customer login](https://strauss-bock.de/kundenlogin/) | 2026-10-23 |
| Wolf-Immobilien-Management GmbH | Facilioo app for tenants and owners | Customer app | [Management services](https://www.w-i-m-immobilien.de/verwaltung) | 2026-10-23 |

## Historical reference — current use unconfirmed

| Property manager | What the source establishes | Evidence | Source | Checked |
| --- | --- | --- | --- | --- |
| Promeda Hausverwaltung GmbH | Company history records introduction of Facilioo as a cloud/customer portal in **2020**; continued use in 2026 is not established by this source | Historical reference | [Company history](https://www.promeda.de/ueber-uns/) | 2026-10-23 |

A provider can change software or operate several different portals at the
same time. Information from a privacy policy or provider website may remain
online after a transition. Entries should be revised or moved to the
historical section when evidence changes.

## Contributing evidence or compatibility reports

To add or update a provider, open a documentation pull request with a
**first-party source URL**, the exact product or relationship it describes,
the source's publication date if available, and the **date you reviewed it**.
Keep reports of actual integration compatibility separate from publicly
documented product use. An integration compatibility claim should identify
the tested release, type of resident account, authentication path, and
available meter types, **without personal or account-specific details**.

Do **not** include credentials, access tokens, residents' names or addresses,
meter IDs, screenshots of private portals, unredacted diagnostics, or real
API responses in public issues or pull requests. See
[SECURITY.md](../SECURITY.md) and [CONTRIBUTING.md](../CONTRIBUTING.md).
