"""Customer list and detail endpoints."""

from __future__ import annotations


def test_list_customers_returns_a_page(client, stored_customers) -> None:
    response = client.get("/api/customers")
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["total"] == 3
    assert body["meta"]["limit"] == 20
    assert body["meta"]["offset"] == 0
    ids = [item["customer_id"] for item in body["items"]]
    assert ids == ["AAA0-AAAAA", "BBB0-BBBBB", "CCC0-CCCCC"]
    assert all(item["latest_prediction"] is None for item in body["items"])


def test_list_customers_pagination(client, stored_customers) -> None:
    first = client.get("/api/customers", params={"limit": 2, "offset": 0})
    second = client.get("/api/customers", params={"limit": 2, "offset": 2})

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(first.json()["items"]) == 2
    assert len(second.json()["items"]) == 1
    assert first.json()["meta"]["total"] == 3
    assert second.json()["items"][0]["customer_id"] == "CCC0-CCCCC"


def test_list_customers_rejects_oversized_page(client) -> None:
    response = client.get("/api/customers", params={"limit": 500})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_get_existing_customer(client, stored_customers) -> None:
    response = client.get("/api/customers/BBB0-BBBBB")
    assert response.status_code == 200
    body = response.json()
    assert body["customer_id"] == "BBB0-BBBBB"
    assert body["contract"] == "One year"
    assert body["tenure"] == 24
    assert "monthly_charges" in body
    assert "payment_method" in body
    assert body["latest_prediction"] is None


def test_missing_customer_returns_404(client) -> None:
    response = client.get("/api/customers/0000-XXXXX")
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["code"] == "customer_not_found"
    assert body["error"]["details"]["customer_id"] == "0000-XXXXX"
    assert "stack" not in body["error"]["message"].lower()


def test_list_customers_search_by_id(client, stored_customers) -> None:
    response = client.get("/api/customers", params={"q": "BBB0"})
    assert response.status_code == 200
    ids = [item["customer_id"] for item in response.json()["items"]]
    assert ids == ["BBB0-BBBBB"]
    assert response.json()["meta"]["total"] == 1


def test_list_does_not_run_the_model(client, stored_customers, monkeypatch) -> None:
    """Listing must read stored predictions, never score every row on the fly."""

    def _fail(*_args, **_kwargs):
        raise AssertionError("list endpoint must not call the explainer")

    monkeypatch.setattr("ml.src.explainability.explainer.explain_customer", _fail)
    response = client.get("/api/customers")
    assert response.status_code == 200
    assert response.json()["meta"]["total"] == 3
