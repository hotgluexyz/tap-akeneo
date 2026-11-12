"""Akeneo HAL pagination and authenticated, read-only REST extraction."""

from __future__ import annotations

import json
import time
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from functools import cached_property
from typing import cast
from urllib.parse import urljoin, urlsplit

from hotglue_singer_sdk.authenticators import BearerTokenAuthenticator
from hotglue_singer_sdk.streams import RESTStream


class AkeneoStream(RESTStream):
    """Follow HAL next links verbatim, never reconstruct an Akeneo cursor."""

    records_jsonpath = "$._embedded.items[*]"
    primary_keys: list[str] = ["code"]  # noqa: RUF012 - SDK stream declaration
    search_after = False
    supports_limit = True

    @property
    def url_base(self):
        return self.config["base_url"].rstrip("/") + "/api/rest/v1"

    @cached_property
    def authenticator(self):
        return BearerTokenAuthenticator(self, token=self.config["access_token"])

    @property
    def replication_method(self):
        return "FULL_TABLE" if self.config["full_table"] else super().replication_method

    def get_url_params(self, context, next_page_token):
        params = {"limit": self.config["page_size"]} if self.supports_limit else {}
        if self.search_after:
            params["pagination_type"] = "search_after"
        if self.replication_method == "INCREMENTAL":
            start = self.get_starting_timestamp(context)
            if start:
                # Akeneo only documents strict >, with second-precision filters.
                # Replay the boundary second so equal timestamps cannot be lost.
                lower = datetime.fromtimestamp(start.timestamp(), timezone.utc) - timedelta(
                    seconds=1
                )
                params["search"] = json.dumps(
                    {"updated": [{"operator": ">", "value": lower.strftime("%Y-%m-%d %H:%M:%S")}]}
                )
        return params

    def get_next_page_token(self, response, previous_token):
        return response.json().get("_links", {}).get("next", {}).get("href")

    def parse_response(self, response):
        items = response.json().get("_embedded", {}).get("items")
        if not isinstance(items, list) or any(not isinstance(row, dict) for row in items):
            raise ValueError(f"{self.name} did not return an Akeneo HAL items collection")
        yield from items

    def prepare_request(self, context, next_page_token):
        if not next_page_token:
            return super().prepare_request(context, next_page_token)
        url = urljoin(self.get_url(context), next_page_token)
        expected, actual = urlsplit(self.get_url(context)), urlsplit(url)
        # Never send an access token to a host/path supplied by an unsafe next link.
        if (actual.scheme, actual.netloc, actual.path) != (
            expected.scheme,
            expected.netloc,
            expected.path,
        ) or actual.fragment:
            raise ValueError("Akeneo pagination link must stay on the same resource and origin")
        return self.build_prepared_request(
            method="GET", url=url, headers=self.http_headers, params={}
        )

    def validate_response(self, response):
        if response.status_code == 429:
            value = response.headers.get("Retry-After")
            if value:
                try:
                    delay = float(value)
                except ValueError:
                    delay = (
                        parsedate_to_datetime(value) - datetime.now(timezone.utc)
                    ).total_seconds()
                time.sleep(max(0, delay))
        # SDK retries 429/5xx at most five times, with exponential backoff/jitter.
        super().validate_response(response)

    def post_process(self, row, context=None):
        if context:
            row = {**row, **context}
        if any(row.get(key) is None for key in cast(list[str], self.primary_keys)):
            raise ValueError(f"{self.name} response is missing its primary key")
        return row
