"""Akeneo tap class."""

from __future__ import annotations

from urllib.parse import urlsplit

from hotglue_singer_sdk import Stream, Tap
from hotglue_singer_sdk import typing as th  # JSON schema typing helpers
from typing_extensions import override

from tap_akeneo.streams import (
    AssetFamiliesStream,
    AssetsStream,
    AssociationTypesStream,
    AttributeGroupsStream,
    AttributeOptionsStream,
    AttributesStream,
    CategoriesStream,
    ChannelsStream,
    CurrenciesStream,
    FamiliesStream,
    FamilyVariantsStream,
    LocalesStream,
    MediaFilesStream,
    ProductModelsStream,
    ProductsStream,
    ReferenceEntitiesStream,
    ReferenceEntityRecordsStream,
)

STREAM_TYPES = [
    AssociationTypesStream,
    AttributeGroupsStream,
    AttributeOptionsStream,
    AttributesStream,
    CategoriesStream,
    ChannelsStream,
    CurrenciesStream,
    FamiliesStream,
    FamilyVariantsStream,
    LocalesStream,
    MediaFilesStream,
    ProductModelsStream,
    ProductsStream,
]

ENTERPRISE_STREAM_TYPES = [
    AssetFamiliesStream,
    AssetsStream,
    ReferenceEntitiesStream,
    ReferenceEntityRecordsStream,
]


class TapAkeneo(Tap):
    """Singer tap for Akeneo."""

    name = "tap-akeneo"

    config_jsonschema = th.PropertiesList(
        th.Property(
            "start_date",
            th.DateTimeType,
            description="Initial products/product-models watermark; ignored for full snapshots",
        ),
        th.Property(
            "base_url",
            th.StringType,
            required=True,
            description="HTTPS PIM instance URL, e.g. https://your-pim.cloud.akeneo.com",
        ),
        th.Property(
            "access_token",
            th.StringType,
            required=True,
            description="Sensitive permanent Akeneo App OAuth access token; no refresh",
        ),
        th.Property("page_size", th.IntegerType, default=100),
        th.Property(
            "full_table",
            th.BooleanType,
            default=True,
            description="Full snapshots for catalog joins; false enables incremental products/models",
        ),
        th.Property(
            "include_enterprise",
            th.BooleanType,
            default=False,
            description="Expose Asset Manager and reference-entity streams (requires EE and scopes)",
        ),
    ).to_dict()
    config_jsonschema["properties"]["page_size"].update(minimum=1, maximum=100)

    @override
    def discover_streams(self) -> list[Stream]:
        """Return a list of discovered streams."""
        url = urlsplit(self.config["base_url"])
        if (
            url.scheme != "https"
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
        ):
            raise ValueError(
                "base_url must be an HTTPS PIM URL without credentials, query or fragment"
            )
        if not self.config["access_token"].strip():
            raise ValueError("access_token must not be empty")
        classes = STREAM_TYPES + (
            ENTERPRISE_STREAM_TYPES if self.config["include_enterprise"] else []
        )
        return [stream_class(tap=self) for stream_class in classes]


if __name__ == "__main__":
    TapAkeneo.cli()
