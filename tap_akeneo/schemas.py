"""Documented top-level fields; tenant-defined nested values stay lossless.

Based on Akeneo's REST reference and OpenAPI 3.1 specification. Dynamic attribute
codes, localized labels, associations and arbitrary value data must not be flattened
or narrowed to one tenant's schema. No network access is needed for discovery.
"""

from __future__ import annotations

from typing import Any


def schema(
    *, strings=(), objects=(), arrays=(), booleans=(), integers=(), extra=None
) -> dict[str, Any]:
    """Build reusable nullable catalog field types without guessing attribute codes."""
    properties: dict[str, Any] = {
        "_links": {"type": ["object", "null"], "additionalProperties": True}
    }
    for fields, kind in [
        (strings, "string"),
        (objects, "object"),
        (arrays, "array"),
        (booleans, "boolean"),
        (integers, "integer"),
    ]:
        for name in fields:
            properties[name] = {"type": [kind, "null"]}
            if kind == "object":
                properties[name]["additionalProperties"] = True
            if kind == "array":
                properties[name]["items"] = {}
    properties.update(extra or {})
    for name in ("created", "updated"):
        if name in properties:
            properties[name]["format"] = "date-time"
    return {"type": "object", "properties": properties}


PRODUCT = schema(
    strings=("uuid", "identifier", "family", "parent", "root_parent", "created", "updated"),
    objects=(
        "values",
        "associations",
        "quantified_associations",
        "metadata",
        "proposal_review_status",
        "readiness",
    ),
    arrays=(
        "categories",
        "groups",
        "quality_scores",
        "completenesses",
        "workflow_execution_statuses",
    ),
    booleans=("enabled",),
)
PRODUCT_MODEL = schema(
    strings=("code", "family", "family_variant", "parent", "created", "updated"),
    objects=(
        "values",
        "associations",
        "quantified_associations",
        "metadata",
        "proposal_review_status",
        "readiness",
    ),
    arrays=("categories", "quality_scores", "workflow_execution_statuses"),
)
CATEGORY = schema(
    strings=("code", "parent", "updated"),
    objects=("labels", "values", "validations"),
    arrays=("channel_requirements",),
    integers=("position",),
)
FAMILY = schema(
    strings=("code", "attribute_as_label", "attribute_as_image", "parent"),
    arrays=("attributes",),
    objects=("attribute_requirements", "labels"),
)
FAMILY_VARIANT = schema(
    strings=("code", "family_code"),
    arrays=("common_attributes", "variant_attribute_sets"),
    objects=("labels",),
)
ATTRIBUTE = schema(
    strings=(
        "code",
        "type",
        "group",
        "validation_rule",
        "validation_regexp",
        "number_min",
        "number_max",
        "metric_family",
        "default_metric_unit",
        "date_min",
        "date_max",
        "max_file_size",
        "reference_data_name",
        "decimal_places_strategy",
    ),
    objects=("labels", "group_labels", "color_configuration", "attribute_metadata"),
    integers=("sort_order", "max_characters"),
    booleans=(
        "localizable",
        "scopable",
        "unique",
        "useable_as_grid_filter",
        "wysiwyg_enabled",
        "decimals_allowed",
        "negative_allowed",
        "display_time",
        "is_main_identifier",
        "is_mandatory",
        "is_pinned",
        "enable_option_creation_during_import",
    ),
    arrays=("available_locales", "allowed_extensions", "table_configuration"),
    extra={
        "default_value": {},
        "decimal_places": {"type": ["number", "null"]},
        "max_items_count": {"type": ["number", "null"]},
    },
)
ATTRIBUTE_OPTION = schema(
    strings=("code", "attribute", "attribute_code"),
    integers=("sort_order",),
    objects=("labels",),
)
ATTRIBUTE_GROUP = schema(
    strings=("code",),
    integers=("sort_order",),
    arrays=("attributes",),
    objects=("labels",),
)
ASSOCIATION_TYPE = schema(
    strings=("code",),
    objects=("labels",),
    booleans=("is_quantified", "is_two_way"),
    extra={"rule": {}},
)
CHANNEL = schema(
    strings=("code", "category_tree"),
    arrays=("locales", "currencies"),
    objects=("conversion_units", "labels"),
)
LOCALE = schema(strings=("code",), booleans=("enabled",))
CURRENCY = schema(strings=("code", "label"), booleans=("enabled",))
MEDIA_FILE = schema(
    strings=("code", "original_filename", "mime_type", "extension"),
    integers=("size",),
)
ASSET_FAMILY = schema(
    strings=("code", "attribute_as_main_media"),
    objects=("labels", "naming_convention"),
    arrays=("product_link_rules", "transformations"),
    booleans=("sharing_enabled", "auto_tagging_enabled"),
)
ASSET = schema(
    strings=("code", "asset_family_code", "created", "updated"),
    objects=("values",),
)
REFERENCE_ENTITY = schema(strings=("code", "image"), objects=("labels",))
REFERENCE_RECORD = schema(
    strings=("code", "reference_entity_code", "created", "updated"),
    objects=("values",),
)
