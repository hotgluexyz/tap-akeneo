# tap-akeneo

Read-only Akeneo PIM REST Singer tap, built with `hotglue-singer-sdk==1.0.51`
and Python **3.10**. Intended for catalog enrichment before indexing in Coveo.

## Status and API choice

Implemented against Akeneo's REST documentation and published OpenAPI 3.1
specification, with offline HTTP fixtures. **No live Akeneo sandbox, OAuth
consent, or production job has been tested.** No credentials are included.

REST exposes the catalog and metadata endpoints directly. GraphQL aggregates
REST resources and does not remove the same authentication requirements.
Products use the recommended UUID API, preserving identity even when an item
does not have a SKU/identifier.

## Streams

All paths are relative to `{base_url}/api/rest/v1`. Discovery is offline.
All streams default to full snapshots. Only products and product models can
use `updated` incremental replication when `full_table=false`.

| Stream | GET path | Primary key |
| --- | --- | --- |
| products | `/products-uuid` | uuid |
| product_models | `/product-models` | code |
| categories | `/categories` | code |
| families | `/families` | code |
| family_variants | `/families/{family_code}/variants` | family_code + code |
| attributes | `/attributes` | code |
| attribute_options | `/attributes/{attribute_code}/options` | attribute_code + code |
| attribute_groups | `/attribute-groups` | code |
| association_types | `/association-types` | code |
| channels | `/channels` | code |
| locales | `/locales` | code |
| currencies | `/currencies` | code |
| media_files | `/media-files` | code |

`include_enterprise=true` additionally exposes these edition/scope-dependent
streams; selecting an inaccessible endpoint fails visibly rather than silently
returning incomplete data:

| Stream | GET path | Primary key |
| --- | --- | --- |
| asset_families | `/asset-families` | code |
| assets | `/asset-families/{asset_family_code}/assets` | asset_family_code + code |
| reference_entities | `/reference-entities` | code |
| reference_entity_records | `/reference-entities/{reference_entity_code}/records` | reference_entity_code + code |

Child streams traverse parents even when only the child is selected. Attribute
options are requested only for simple/multiple-select attributes. Parent-scoped
keys prevent collisions between repeated option/record codes.

## Catalog data contract for Coveo

* Products retain UUID, identifier, parent model, family, category codes,
  enabled status, associations and tenant-defined `values`.
* Localized/channel-scoped values remain nested and unchanged: names,
  descriptions, brands, colors, sizes, custom attributes, metrics and price
  collections (amount and currency) are not flattened to a single locale.
* Product models retain inherited values and their parent chain; family variants
  expose the axes and attribute sets needed to resolve variants downstream.
* Categories preserve labels and parent codes; attributes/options preserve
  type definitions and localized display labels.
* Media files preserve metadata and API download links. **No image binaries
  are downloaded or published to a public CDN.** Authenticated Akeneo download
  URLs are not automatically usable as public Coveo image URLs.

This is extraction, **not an Akeneo-to-Coveo ETL**. Downstream mapping must
resolve model inheritance, channel/locale, select-option labels, categories,
public media hosting and Coveo document/commerce fields. Do not apply the
commercetools ETL directly to Akeneo records.

Akeneo has no universal stock/warehouse inventory endpoint in this scope.
Inventory, sale prices and customer-specific pricing are available only if
the tenant models them as attributes or another system supplies them. No
discounts or stock are invented by the tap. No deletion/tombstone stream or
automatic removal of previously indexed Coveo documents is implemented.

## Authentication and connector handoff

The tap consumes an Akeneo **App permanent bearer access token**. It never
performs OAuth consent or refresh. Tenant-supplied client ID/secret belong to
the Hotglue OAuth backend, not the tap's extraction config.

Akeneo Apps uses a custom authorization-code exchange: a random hexadecimal
`code_identifier` and SHA-256 of `code_identifier + client_secret`. This is
**not standard PKCE or client credentials**. Tokens do not expire and have no
refresh token; revoked tokens require reauthorization. Legacy Connections
instead require username/password and are not implemented here.

The companion `akeneo-connector/` handoff (a sibling directory in the working
Sales-Engineering repository) includes a **disabled** available connector
definition and the backend exchange requirements. It cannot be enabled until
that backend integration is implemented/tested and the published tap install
URI is supplied. Client ID and secret alone do not make the JSON functional.

Core read scopes: `read_products`, `read_catalog_structure`,
`read_attribute_options`, `read_categories`, `read_channel_localization`,
`read_channel_settings`. Enterprise assets/reference entities require their
additional read scopes and user permissions; the draft connector does not
request those scopes by default. PIM edition, App access grants and user
permissions determine actual data visibility.

## Configuration

| Setting | Required | Default | Meaning |
| --- | --- | --- | --- |
| base_url | yes | — | HTTPS PIM instance URL, not an API endpoint |
| access_token | yes | — | Sensitive permanent App bearer token |
| page_size | no | 100 | Integer 1–100, used where supported |
| full_table | no | true | Complete snapshots for catalog joins |
| start_date | no | unset | ISO8601 initial products/models watermark; only when full_table=false |
| include_enterprise | no | false | Expose asset/reference-entity streams |

Example `config.json` (keep real values in a secret store, never Git):

```json
{
  "base_url": "https://your-pim.cloud.akeneo.com",
  "access_token": "YOUR_APP_ACCESS_TOKEN",
  "full_table": true,
  "page_size": 100,
  "include_enterprise": false
}
```

## Install and run

```bash
python3.10 -m venv .venv
.venv/bin/pip install -e .
.venv/bin/tap-akeneo --config config.json --discover > catalog.json
.venv/bin/tap-akeneo --config config.json --catalog catalog-selected.json > data.singer
```

Select the required streams/fields in a copy of the discovered catalog before
syncing. State can be supplied with `--state state.json`; persist emitted Singer
STATE messages through the target/orchestrator. Environment configuration is
supported with `--config=ENV`; `.env.example` documents `TAP_AKENEO_*` names.

### Replication, pagination and failures

Products/models use search-after pagination; other core collections use offset
pagination. Follow HAL `_links.next.href` verbatim, retaining encoded cursors.
Enterprise endpoints do not receive unsupported limit/pagination parameters.
Next links changing origin or resource path are rejected before sending tokens.

Full snapshots ignore saved incremental catalogs/watermarks. With
`full_table=false`, products/models filter `updated > watermark minus 1 second`
and retain the maximum timestamp even when records arrive out of timestamp
order. Replayed boundary records are expected; targets must upsert by key.
Second-precision filters use **UTC**, appropriate for SaaS/default UTC servers;
non-UTC self-hosted server semantics are not validated. Metadata remains full
snapshot. Incremental extraction does not resolve downstream dependency
fan-out, removed records, or changing visibility: use full snapshots for the
initial Coveo integration.

HTTP 429 honors numeric/date `Retry-After` and SDK bounded retries; 5xx uses
SDK backoff/jitter. Authorization/permission/missing-endpoint/validation errors
fail the job. Malformed HAL collections and missing primary keys fail rather
than silently dropping data. Dynamic nested fields are retained through the
Singer schema; new unknown top-level fields require an explicit schema update.

## Offline verification

```bash
.venv/bin/pip install tox tox-uv
.venv/bin/tox
```

Runs Ruff, mypy, ty and Python 3.10 tests. Fixtures exercise actual Singer
output, schema validation, nested localized values/prices, search-after and
offset next links, parent-scoped streams, unordered incremental watermarks,
full-snapshot overrides, retries and failures. Mocks do not prove real OAuth
or API acceptance. Live acceptance still requires a customer-authorized App,
representative catalog and completed Hotglue OAuth backend integration.

Additional local validation compared all 17 collection paths, supported query
parameters and documented top-level fields against the downloaded OpenAPI
specification: no documented top-level fields were missing. A full mocked
17-stream sync was also passed through the official `target-parquet` 0.0.21;
every populated fixture field survived, including parent keys and nested
localized prices/custom values. That target serializes objects/arrays as JSON
strings in Parquet: the future ETL must decode them before mapping to Coveo.

## References

* [REST reference](https://api.akeneo.com/api-reference-index.html)
* [GraphQL introduction](https://api.akeneo.com/graphql/getting-started.html)
* [Official published OpenAPI specification](https://storage.googleapis.com/akecld-prd-pim-saas-shared-openapi-spec/openapi.json)
* [Apps authentication](https://api.akeneo.com/apps/authentication-and-authorization.html)
* [Pagination](https://api.akeneo.com/documentation/pagination.html)
* [Filters](https://api.akeneo.com/documentation/filter.html)

MIT — see `LICENSE`.
