"""Exercise the public Singer output against documented Akeneo HTTP fixtures."""

import json
from urllib.parse import parse_qs, urlsplit

import jsonschema
import pytest
import responses
from hotglue_singer_sdk.exceptions import ConfigValidationError, FatalAPIError

from tap_akeneo.tap import TapAkeneo

BASE = "https://fixture.akeneo.example"
API = BASE + "/api/rest/v1"
CONFIG = {"base_url": BASE, "access_token": "fixture-only-token", "page_size": 2}


def page(items, next_url=None):
    return {
        "_embedded": {"items": items},
        "_links": {"next": {"href": next_url}} if next_url else {},
    }


def messages(capsys):
    result = [
        json.loads(line) for line in capsys.readouterr().out.splitlines() if line.startswith("{")
    ]
    schemas = {m["stream"]: m["schema"] for m in result if m["type"] == "SCHEMA"}
    for m in result:
        if m["type"] == "RECORD":
            jsonschema.validate(m["record"], schemas[m["stream"]])
    return result


@responses.activate
def test_products_singer_retains_values_and_verbatim_cursor(capsys):
    values = {
        "title": [
            {"locale": "en_US", "scope": "ecommerce", "data": "Alpine shell"},
            {"locale": "de_DE", "scope": "ecommerce", "data": "Alpenjacke"},
        ],
        "price": [
            {
                "locale": None,
                "scope": None,
                "data": [
                    {"amount": "189.95", "currency": "USD"},
                    {"amount": "173.31", "currency": "EUR"},
                ],
            }
        ],
        "weight": [{"locale": None, "scope": None, "data": {"amount": "0.43", "unit": "KILOGRAM"}}],
        "image": [{"locale": None, "scope": None, "data": "a/b/shell.jpg"}],
        "custom": [{"locale": None, "scope": None, "data": {"arbitrary": [False, 0, None]}}],
    }
    rows = [
        {
            "uuid": "id-a",
            "identifier": "SKU-A",
            "parent": "shell-red",
            "enabled": True,
            "family": "apparel",
            "categories": ["jackets"],
            "values": values,
            "updated": "2026-01-03T10:00:00Z",
            "associations": {"UPSELL": {"products": ["id-b"]}},
        },
        {"uuid": "id-b", "identifier": None, "parent": None, "enabled": False, "values": {}},
    ]
    next_url = API + "/products-uuid?pagination_type=search_after&search_after=a%2Fb%2Bz&limit=2"
    responses.get(API + "/products-uuid", json=page(rows[:1], next_url))
    responses.get(
        next_url,
        json=page(rows[1:]),
        match=[responses.matchers.query_string_matcher(urlsplit(next_url).query)],
    )
    tap = TapAkeneo(config=CONFIG)
    tap.streams["products"].sync()
    emitted = [m["record"] for m in messages(capsys) if m["type"] == "RECORD"]
    assert emitted == rows
    assert responses.calls[1].request.url == next_url
    assert all(
        c.request.headers["Authorization"] == "Bearer fixture-only-token" for c in responses.calls
    )


@responses.activate
def test_child_only_selection_traverses_parents_and_qualifies_repeated_codes(capsys):
    tap = TapAkeneo(config=CONFIG)
    catalog = tap.catalog.to_dict()
    for entry in catalog["streams"]:
        for md in entry["metadata"]:
            if not md["breadcrumb"]:
                md["metadata"]["selected"] = entry["stream"] == "attribute_options"
    responses.get(
        API + "/attributes",
        json=page(
            [
                {"code": "color", "type": "pim_catalog_simpleselect"},
                {"code": "material", "type": "pim_catalog_multiselect"},
                {"code": "description", "type": "pim_catalog_textarea"},
            ]
        ),
    )
    for attribute, label in [("color", "Red"), ("material", "Wool")]:
        responses.get(
            API + f"/attributes/{attribute}/options",
            json=page(
                [
                    {
                        "code": "same-code",
                        "attribute": attribute,
                        "labels": {"en_US": label},
                        "sort_order": 0,
                    }
                ]
            ),
        )
    TapAkeneo(config=CONFIG, catalog=catalog).sync_all()
    emitted = [m for m in messages(capsys) if m["type"] == "RECORD"]
    assert {m["stream"] for m in emitted} == {"attribute_options"}
    assert [(m["record"]["attribute_code"], m["record"]["code"]) for m in emitted] == [
        ("color", "same-code"),
        ("material", "same-code"),
    ]
    assert len(responses.calls) == 3  # No unsupported description/options request.


@responses.activate
def test_family_variants_retain_family_and_axes(capsys):
    responses.get(API + "/families", json=page([{"code": "clothing"}, {"code": "shoes"}]))
    for family, axis in [("clothing", "size"), ("shoes", "shoe_size")]:
        responses.get(
            API + f"/families/{family}/variants",
            json=page(
                [
                    {
                        "code": "by_size",
                        "variant_attribute_sets": [
                            {"level": 1, "axes": [axis], "attributes": [axis]}
                        ],
                    }
                ]
            ),
        )
    tap = TapAkeneo(config=CONFIG)
    tap.streams["families"].sync()
    emitted = [
        m["record"]
        for m in messages(capsys)
        if m["type"] == "RECORD" and m["stream"] == "family_variants"
    ]
    assert [(r["family_code"], r["variant_attribute_sets"][0]["axes"]) for r in emitted] == [
        ("clothing", ["size"]),
        ("shoes", ["shoe_size"]),
    ]


@responses.activate
def test_categories_follow_offset_links_and_keep_localized_tree(capsys):
    rows = [
        {"code": "outdoors", "parent": None, "labels": {"en_US": "Outdoors"}},
        {"code": "jackets", "parent": "outdoors", "labels": {"de_DE": "Jacken"}},
    ]
    responses.get(API + "/categories", json=page(rows[:1], API + "/categories?page=2&limit=2"))
    responses.get(
        API + "/categories?page=2&limit=2",
        json=page(rows[1:]),
        match=[responses.matchers.query_param_matcher({"page": "2", "limit": "2"})],
    )
    TapAkeneo(config=CONFIG).streams["categories"].sync()
    assert [m["record"] for m in messages(capsys) if m["type"] == "RECORD"] == rows


@responses.activate
def test_incremental_unordered_watermarks_replay_boundary(capsys):
    state = {
        "bookmarks": {
            "products": {
                "replication_key": "updated",
                "replication_key_value": "2026-01-02T10:00:00Z",
            }
        }
    }
    rows = [
        {"uuid": "z", "updated": "2026-01-03T11:00:00Z", "values": {}},
        {"uuid": "a", "updated": "2026-01-02T10:00:00Z", "values": {}},
    ]
    responses.get(API + "/products-uuid", json=page(rows))
    tap = TapAkeneo(config=CONFIG | {"full_table": False}, state=state)
    catalog = tap.catalog.to_dict()
    for entry in catalog["streams"]:
        for md in entry["metadata"]:
            if not md["breadcrumb"]:
                md["metadata"]["selected"] = entry["stream"] == "products"
    tap = TapAkeneo(config=CONFIG | {"full_table": False}, state=state, catalog=catalog)
    tap.sync_all()
    emitted = messages(capsys)
    assert [m["record"] for m in emitted if m["type"] == "RECORD"] == rows
    query = parse_qs(urlsplit(str(responses.calls[0].request.url)).query)
    assert json.loads(query["search"][0]) == {
        "updated": [{"operator": ">", "value": "2026-01-02 09:59:59"}]
    }
    assert tap.state["bookmarks"]["products"]["replication_key_value"] == "2026-01-03T11:00:00Z"


@responses.activate
def test_full_snapshot_overrides_saved_catalog_and_watermark():
    old = TapAkeneo(config=CONFIG | {"full_table": False}).catalog.to_dict()
    state = {
        "bookmarks": {
            "products": {
                "replication_key": "updated",
                "replication_key_value": "2026-01-02T10:00:00Z",
            }
        }
    }
    responses.get(API + "/products-uuid", json=page([]))
    stream = TapAkeneo(config=CONFIG, catalog=old, state=state).streams["products"]
    assert list(stream.get_records(None)) == []
    assert "search" not in parse_qs(urlsplit(str(responses.calls[0].request.url)).query)


@responses.activate
@pytest.mark.parametrize(
    "url",
    [
        "https://evil.example/api/rest/v1/products-uuid?page=2",
        "http://fixture.akeneo.example/api/rest/v1/products-uuid?page=2",
        API + "/categories?page=2",
    ],
)
def test_pagination_cannot_send_token_to_another_origin_or_resource(url):
    responses.get(API + "/products-uuid", json=page([{"uuid": "one"}], url))
    with pytest.raises(ValueError, match="pagination link"):
        list(TapAkeneo(config=CONFIG).streams["products"].get_records(None))
    assert len(responses.calls) == 1


@responses.activate
@pytest.mark.parametrize("status", [401, 403, 404, 422])
def test_permission_edition_and_filter_errors_are_not_silently_empty(status):
    responses.get(
        API + "/products-uuid", json={"code": status, "message": "Not available"}, status=status
    )
    with pytest.raises(FatalAPIError):
        list(TapAkeneo(config=CONFIG).streams["products"].get_records(None))
    assert len(responses.calls) == 1


@responses.activate
def test_throttle_retry_preserves_records(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda _: None)
    responses.get(API + "/products-uuid", status=429, headers={"Retry-After": "2"})
    responses.get(API + "/products-uuid", json=page([{"uuid": "after-throttle"}]))
    assert list(TapAkeneo(config=CONFIG).streams["products"].get_records(None)) == [
        {"uuid": "after-throttle"}
    ]


@responses.activate
@pytest.mark.parametrize(
    "body", [{}, {"_embedded": {"items": {}}}, {"_embedded": {"items": [None]}}]
)
def test_malformed_collections_fail(body):
    responses.get(API + "/products-uuid", json=body)
    with pytest.raises(ValueError, match="HAL items"):
        list(TapAkeneo(config=CONFIG).streams["products"].get_records(None))


@pytest.mark.parametrize("size", [0, 101])
def test_page_size_bounds(size):
    with pytest.raises(ConfigValidationError, match="page_size"):
        TapAkeneo(config=CONFIG | {"page_size": size})


def test_enterprise_is_explicit_opt_in_and_discovery_is_offline():
    base = TapAkeneo(config=CONFIG).catalog.to_dict()["streams"]
    enterprise = TapAkeneo(config=CONFIG | {"include_enterprise": True}).catalog.to_dict()[
        "streams"
    ]
    assert len(base) == 13 and len(enterprise) == 17
    assert {s["stream"] for s in enterprise} - {s["stream"] for s in base} == {
        "asset_families",
        "assets",
        "reference_entities",
        "reference_entity_records",
    }


@responses.activate
@pytest.mark.parametrize(
    "parent,child,field,path",
    [
        ("asset_families", "assets", "asset_family_code", "asset-families"),
        (
            "reference_entities",
            "reference_entity_records",
            "reference_entity_code",
            "reference-entities",
        ),
    ],
)
def test_enterprise_children_preserve_dynamic_values_without_unsupported_params(
    capsys, parent, child, field, path
):
    data = {"label": [{"locale": "en_US", "channel": None, "data": "Northline"}]}
    responses.get(API + f"/{path}", json=page([{"code": "brands"}]))
    suffix = "assets" if child == "assets" else "records"
    responses.get(
        API + f"/{path}/brands/{suffix}", json=page([{"code": "northline", "values": data}])
    )
    tap = TapAkeneo(config=CONFIG | {"include_enterprise": True})
    tap.streams[parent].sync()
    rows = [m["record"] for m in messages(capsys) if m["type"] == "RECORD" and m["stream"] == child]
    assert rows == [{"code": "northline", "values": data, field: "brands"}]
    assert all(not urlsplit(c.request.url).query for c in responses.calls)
