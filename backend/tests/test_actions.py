"""Human-review action tracking. No external side effects."""

from __future__ import annotations


def _create(client, customer_id: str = "AAA0-AAAAA", **extra) -> dict:
    payload = {
        "customer_id": customer_id,
        "strategy_id": "CONTRACT_CONVERSION",
        "recommendation": "Offer a longer-term contract after human review.",
    }
    payload.update(extra)
    response = client.post("/api/actions", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_create_action_starts_pending(client, stored_customers) -> None:
    body = _create(client)
    assert body["status"] == "PENDING"
    assert body["id"] >= 1
    assert body["strategy_id"] == "CONTRACT_CONVERSION"


def test_create_action_for_missing_customer(client) -> None:
    response = client.post(
        "/api/actions",
        json={
            "customer_id": "0000-XXXXX",
            "strategy_id": "CONTRACT_CONVERSION",
            "recommendation": "Would never be stored.",
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "customer_not_found"


def test_approve_action(client, stored_customers) -> None:
    created = _create(client)
    response = client.patch(f"/api/actions/{created['id']}", json={"status": "APPROVED"})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "APPROVED"
    assert body["reviewed_by_sub"] == "auth0|test-reviewer"
    assert body["reviewed_by_email"] == "reviewer@example.test"
    assert body["reviewed_by_name"] == "Test Reviewer"


def test_reject_requires_a_note(client, stored_customers) -> None:
    created = _create(client)
    missing = client.patch(f"/api/actions/{created['id']}", json={"status": "REJECTED"})
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "reviewer_note_required"

    rejected = client.patch(
        f"/api/actions/{created['id']}",
        json={"status": "REJECTED", "reviewer_note": "Customer already leaving."},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "REJECTED"
    assert rejected.json()["reviewer_note"] == "Customer already leaving."


def test_modify_requires_a_note_and_can_revise_wording(client, stored_customers) -> None:
    created = _create(client)
    response = client.patch(
        f"/api/actions/{created['id']}",
        json={
            "status": "MODIFIED",
            "reviewer_note": "Drop the contract incentive; offer support instead.",
            "recommendation": "Offer priority support after specialist review.",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "MODIFIED"
    assert body["recommendation"] == "Offer priority support after specialist review."


def test_modified_action_can_later_be_approved(client, stored_customers) -> None:
    created = _create(client)
    client.patch(
        f"/api/actions/{created['id']}",
        json={"status": "MODIFIED", "reviewer_note": "Reworded."},
    )
    approved = client.patch(f"/api/actions/{created['id']}", json={"status": "APPROVED"})
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"


def test_approved_action_cannot_be_changed(client, stored_customers) -> None:
    created = _create(client)
    client.patch(f"/api/actions/{created['id']}", json={"status": "APPROVED"})
    again = client.patch(
        f"/api/actions/{created['id']}",
        json={"status": "REJECTED", "reviewer_note": "too late"},
    )
    assert again.status_code == 409
    assert again.json()["error"]["code"] == "invalid_action_transition"
    assert again.json()["error"]["details"]["current_status"] == "APPROVED"


def test_cannot_create_an_approved_action(client, stored_customers) -> None:
    """The create schema has no status field, so auto-approval is unrepresentable."""
    response = client.post(
        "/api/actions",
        json={
            "customer_id": "AAA0-AAAAA",
            "strategy_id": "CONTRACT_CONVERSION",
            "recommendation": "Approve me please.",
            "status": "APPROVED",
        },
    )
    # Extra fields are ignored or rejected; either way the stored row is PENDING.
    if response.status_code == 201:
        assert response.json()["status"] == "PENDING"
    else:
        assert response.status_code == 422


def test_list_actions_filters(client, stored_customers) -> None:
    first = _create(client, customer_id="AAA0-AAAAA")
    _create(client, customer_id="BBB0-BBBBB")
    client.patch(f"/api/actions/{first['id']}", json={"status": "APPROVED"})

    pending = client.get("/api/actions", params={"status": "PENDING"})
    approved = client.get("/api/actions", params={"status": "APPROVED"})
    for_a = client.get("/api/actions", params={"customer_id": "AAA0-AAAAA"})

    assert pending.json()["meta"]["total"] == 1
    assert approved.json()["meta"]["total"] == 1
    assert for_a.json()["meta"]["total"] == 1
    assert for_a.json()["items"][0]["customer_id"] == "AAA0-AAAAA"


def test_missing_action_returns_404(client) -> None:
    response = client.get("/api/actions/9999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "action_not_found"
