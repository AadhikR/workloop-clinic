import uuid

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.http.errors import install_exception_handlers
from app.http.idempotency import parse_idempotency_key
from app.http.schemas import ApiSchema, CollectionResponse, DataResponse, Page
from app.http.validation import Pagination, parse_pagination, parse_sort, parse_strict_json


class Example(ApiSchema):
    display_name: str


def test_response_helpers_serialize_camel_case_envelopes() -> None:
    item = DataResponse(data=Example(display_name="Synthetic person"))
    collection = CollectionResponse(
        data=[Example(display_name="Synthetic person")],
        page=Page(limit=50, next_cursor=None, has_more=False),
    )

    assert item.model_dump(mode="json", by_alias=True) == {
        "data": {"displayName": "Synthetic person"}
    }
    assert collection.model_dump(mode="json", by_alias=True) == {
        "data": [{"displayName": "Synthetic person"}],
        "page": {"limit": 50, "nextCursor": None, "hasMore": False},
    }


@pytest.mark.parametrize("limit", ["0", "101", "1.5", "text"])
def test_pagination_rejects_invalid_limits(limit: str) -> None:
    with pytest.raises(ValueError):
        parse_pagination(limit=limit, cursor=None)


def test_pagination_uses_contract_defaults() -> None:
    assert parse_pagination(limit=None, cursor=None) == Pagination(limit=50, cursor=None)
    assert parse_pagination(limit="100", cursor="opaque") == Pagination(limit=100, cursor="opaque")


@pytest.mark.parametrize("value", ["", "name,,createdAt", "name,name", "a,b,c,d", "private"])
def test_sort_rejects_empty_duplicate_excess_and_unknown_fields(value: str) -> None:
    with pytest.raises(ValueError):
        parse_sort(value, allowed_fields={"name", "createdAt"}, default=("name",))


def test_sort_accepts_allowlisted_directions() -> None:
    assert parse_sort(
        "-createdAt,name", allowed_fields={"name", "createdAt"}, default=("name",)
    ) == (("createdAt", True), ("name", False))


def test_strict_json_rejects_duplicate_names_and_trailing_data() -> None:
    assert parse_strict_json(b'{"displayName":"Synthetic"}') == {"displayName": "Synthetic"}
    for body in (b'{"name":"one","name":"two"}', b"{} []", b"\xff"):
        with pytest.raises(ValueError):
            parse_strict_json(body)


@pytest.mark.asyncio
async def test_idempotency_header_requires_one_canonical_uuid4() -> None:
    application = FastAPI()
    install_exception_handlers(application)

    async def route(request: Request) -> dict[str, str]:
        return {"key": str(parse_idempotency_key(request, required=True))}

    application.add_api_route("/test", route, methods=["POST"])
    key = str(uuid.uuid4())
    async with AsyncClient(
        transport=ASGITransport(app=application), base_url="http://testserver"
    ) as client:
        accepted = await client.post("/test", headers={"Idempotency-Key": key})
        missing = await client.post("/test")
        malformed = await client.post("/test", headers={"Idempotency-Key": key.upper()})
        duplicate = await client.post(
            "/test", headers=[("Idempotency-Key", key), ("Idempotency-Key", key)]
        )

    assert accepted.json() == {"key": key}
    assert missing.json()["detail"]["code"] == "idempotency_key_required"
    assert malformed.json()["detail"]["code"] == "invalid_idempotency_key"
    assert duplicate.json()["detail"]["code"] == "invalid_idempotency_key"
