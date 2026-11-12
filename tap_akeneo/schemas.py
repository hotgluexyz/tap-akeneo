"""Documented top-level fields; tenant-defined nested values stay lossless.

Based on Akeneo's REST reference and OpenAPI 3.1 specification. Dynamic attribute
codes, localized labels, associations and arbitrary value data must not be flattened
or narrowed to one tenant's schema. No network access is needed for discovery.
"""

from __future__ import annotations

from typing import Any

from hotglue_singer_sdk import typing as th


def schema(
    *, strings=(), objects=(), arrays=(), booleans=(), integers=(), extra=None
) -> dict[str, Any]:
    """Build reusable nullable catalog field types without guessing attribute codes."""
    properties = th.PropertiesList()
    open_object = th.ObjectType(additional_properties=th.CustomType({}))
    properties.append(th.Property("_links", open_object))
    for fields, kind in [
        (strings, th.StringType),
        (objects, open_object),
        (arrays, th.ArrayType(th.CustomType({}))),
        (booleans, th.BooleanType),
        (integers, th.IntegerType),
    ]:
        for name in fields:
            field_type = th.DateTimeType if name in ("created", "updated") else kind
            properties.append(th.Property(name, field_type))
    result = properties.to_dict()
    # SDK 1.0.51 cannot wrap an unconstrained {} in an optional Property.
    # Keep arbitrary values unrestricted; declaring every JSON type would make
    # SDK record conformance coerce them to booleans.
    result["properties"].update(extra or {})
    return result


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
    objects=("labels", "group_labels", "color_configuration", "attribute_metadata", "guidelines"),
    integers=("sort_order", "max_characters", "minimum_input_length"),
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
        "auto_option_sorting": {},
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
