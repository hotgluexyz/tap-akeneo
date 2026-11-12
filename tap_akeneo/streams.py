"""Akeneo catalog streams and parent-scoped metadata endpoints."""

from __future__ import annotations

from tap_akeneo import schemas as s
from tap_akeneo.client import AkeneoStream


class ProductsStream(AkeneoStream):
    """Products, including variant SKUs, parent models and all localized values."""

    name = "products"
    path = "/products-uuid"
    primary_keys = ["uuid"]  # noqa: RUF012 - SDK stream declaration
    replication_key = "updated"
    is_sorted = False  # Search-after orders by primary key, not update timestamp.
    search_after = True
    schema = s.PRODUCT


class ProductModelsStream(AkeneoStream):
    """Root and sub-models preserve Akeneo's multi-level variant hierarchy."""

    name = "product_models"
    path = "/product-models"
    replication_key = "updated"
    is_sorted = False
    search_after = True
    schema = s.PRODUCT_MODEL


class CategoriesStream(AkeneoStream):
    name = "categories"
    path = "/categories"
    schema = s.CATEGORY


class FamiliesStream(AkeneoStream):
    name = "families"
    path = "/families"
    schema = s.FAMILY

    def get_child_context(self, record, context):
        return {"family_code": record["code"]}


class FamilyVariantsStream(AkeneoStream):
    name = "family_variants"
    path = "/families/{family_code}/variants"
    parent_stream_type = FamiliesStream
    primary_keys = ["family_code", "code"]  # noqa: RUF012 - SDK stream declaration
    schema = s.FAMILY_VARIANT


class AttributesStream(AkeneoStream):
    name = "attributes"
    path = "/attributes"
    schema = s.ATTRIBUTE

    def get_child_context(self, record, context):
        return {"attribute_code": record["code"], "attribute_type": record["type"]}


class AttributeOptionsStream(AkeneoStream):
    name = "attribute_options"
    path = "/attributes/{attribute_code}/options"
    parent_stream_type = AttributesStream
    primary_keys = ["attribute_code", "code"]  # noqa: RUF012 - SDK stream declaration
    schema = s.ATTRIBUTE_OPTION

    def get_records(self, context):
        # Non-select attributes do not expose an options collection.
        if context and context["attribute_type"] in (
            "pim_catalog_simpleselect",
            "pim_catalog_multiselect",
        ):
            yield from super().get_records(context)

    def post_process(self, row, context=None):
        assert context is not None  # Options are always traversed under an attribute.
        return super().post_process(row, {"attribute_code": context["attribute_code"]})


class AttributeGroupsStream(AkeneoStream):
    name = "attribute_groups"
    path = "/attribute-groups"
    schema = s.ATTRIBUTE_GROUP


class AssociationTypesStream(AkeneoStream):
    name = "association_types"
    path = "/association-types"
    schema = s.ASSOCIATION_TYPE


class ChannelsStream(AkeneoStream):
    name = "channels"
    path = "/channels"
    schema = s.CHANNEL


class LocalesStream(AkeneoStream):
    name = "locales"
    path = "/locales"
    schema = s.LOCALE


class CurrenciesStream(AkeneoStream):
    name = "currencies"
    path = "/currencies"
    schema = s.CURRENCY


class MediaFilesStream(AkeneoStream):
    """Metadata and authenticated download links, not binary file contents."""

    name = "media_files"
    path = "/media-files"
    schema = s.MEDIA_FILE


class AssetFamiliesStream(AkeneoStream):
    name = "asset_families"
    path = "/asset-families"
    supports_limit = False
    schema = s.ASSET_FAMILY

    def get_child_context(self, record, context):
        return {"asset_family_code": record["code"]}


class AssetsStream(AkeneoStream):
    name = "assets"
    path = "/asset-families/{asset_family_code}/assets"
    parent_stream_type = AssetFamiliesStream
    primary_keys = ["asset_family_code", "code"]  # noqa: RUF012 - SDK stream declaration
    supports_limit = False
    schema = s.ASSET


class ReferenceEntitiesStream(AkeneoStream):
    name = "reference_entities"
    path = "/reference-entities"
    supports_limit = False
    schema = s.REFERENCE_ENTITY

    def get_child_context(self, record, context):
        return {"reference_entity_code": record["code"]}


class ReferenceEntityRecordsStream(AkeneoStream):
    name = "reference_entity_records"
    path = "/reference-entities/{reference_entity_code}/records"
    parent_stream_type = ReferenceEntitiesStream
    primary_keys = ["reference_entity_code", "code"]  # noqa: RUF012 - SDK stream declaration
    supports_limit = False
    schema = s.REFERENCE_RECORD
