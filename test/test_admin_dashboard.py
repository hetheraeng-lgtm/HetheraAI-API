"""Tests for admin dashboard overview and transaction listing/detail endpoints."""

import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.enums.transaction import TransactionStatus, TransactionType
from app.model.transaction import Transaction
from app.model.user import User


async def _register_and_login(client, admin_payload):
    await client.post("/api/v1/auth/admin/register", json=admin_payload)
    login = await client.post(
        "/api/v1/auth/admin/login",
        json={"email": admin_payload["email"], "password": admin_payload["password"]},
    )
    token = login.json()["data"]["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def _seed_user_and_transactions(db_session) -> User:
    user = User(chat_id="08110000001")
    db_session.add(user)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    transactions = [
        Transaction(
            reference=f"TXN{uuid.uuid4().hex.upper()}",
            user_id=user.id,
            type=TransactionType.AIRTIME,
            status=TransactionStatus.SUCCESSFUL,
            amount=Decimal("100.00"),
            provider="mtn",
            service_id="mtn",
            idempotency_key=str(uuid.uuid4()),
            profit_loss=Decimal("5.00"),
            created_at=now,
        ),
        Transaction(
            reference=f"TXN{uuid.uuid4().hex.upper()}",
            user_id=user.id,
            type=TransactionType.CABLE_TV,
            status=TransactionStatus.FAILED,
            amount=Decimal("2000.00"),
            provider="gotv",
            service_id="gotv",
            idempotency_key=str(uuid.uuid4()),
            failure_reason="Provider timeout",
            created_at=now,
        ),
        Transaction(
            reference=f"TXN{uuid.uuid4().hex.upper()}",
            user_id=user.id,
            type=TransactionType.MOBILE_DATA,
            status=TransactionStatus.PROCESSING,
            amount=Decimal("500.00"),
            provider="glo-data",
            service_id="glo-data",
            idempotency_key=str(uuid.uuid4()),
            created_at=now,
        ),
    ]
    db_session.add_all(transactions)
    await db_session.commit()
    return user


class TestDashboardOverview:
    async def test_overview_reflects_seeded_transactions(self, client, db_session, admin_payload):
        headers = await _register_and_login(client, admin_payload)
        await _seed_user_and_transactions(db_session)

        response = await client.get("/api/v1/admin/dashboard/overview?range=30d", headers=headers)
        assert response.status_code == 200
        data = response.json()["data"]

        assert data["total_transactions"] == 3
        assert data["successful_transactions"] == 1
        assert data["failed_transactions"] == 1
        assert data["pending_transactions"] == 1
        assert data["total_customers"] == 1
        assert data["success_rate"] == 50.0

    async def test_overview_requires_auth(self, client):
        response = await client.get("/api/v1/admin/dashboard/overview?range=30d")
        assert response.status_code == 401

    async def test_custom_range_requires_start_and_end_dates(self, client, admin_payload):
        headers = await _register_and_login(client, admin_payload)
        response = await client.get(
            "/api/v1/admin/dashboard/overview?range=custom", headers=headers
        )
        assert response.status_code == 400

    async def test_custom_range_filters_out_of_window_transactions(
        self, client, db_session, admin_payload
    ):
        headers = await _register_and_login(client, admin_payload)
        user = await _seed_user_and_transactions(db_session)

        old_txn = Transaction(
            reference=f"TXN{uuid.uuid4().hex.upper()}",
            user_id=user.id,
            type=TransactionType.AIRTIME,
            status=TransactionStatus.SUCCESSFUL,
            amount=Decimal("999.00"),
            provider="mtn",
            service_id="mtn",
            idempotency_key=str(uuid.uuid4()),
            created_at=datetime.now(timezone.utc) - timedelta(days=90),
        )
        db_session.add(old_txn)
        await db_session.commit()

        start = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        end = datetime.now(timezone.utc).isoformat()
        response = await client.get(
            "/api/v1/admin/dashboard/overview",
            params={"range": "custom", "start_date": start, "end_date": end},
            headers=headers,
        )
        assert response.status_code == 200
        assert response.json()["data"]["total_transactions"] == 3  # excludes the 90-day-old one


class TestAdminTransactions:
    async def test_list_transactions_is_paginated(self, client, db_session, admin_payload):
        headers = await _register_and_login(client, admin_payload)
        await _seed_user_and_transactions(db_session)

        response = await client.get(
            "/api/v1/admin/transactions?page=0&size=2", headers=headers
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["records"]) == 2
        assert data["totalRecords"] == 3
        assert data["totalPages"] == 2

    async def test_list_transactions_filters_by_status(self, client, db_session, admin_payload):
        headers = await _register_and_login(client, admin_payload)
        await _seed_user_and_transactions(db_session)

        response = await client.get(
            "/api/v1/admin/transactions?status=FAILED", headers=headers
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["totalRecords"] == 1
        assert data["records"][0]["status"] == "FAILED"

    async def test_list_transactions_search_matches_chat_id(
        self, client, db_session, admin_payload
    ):
        headers = await _register_and_login(client, admin_payload)
        await _seed_user_and_transactions(db_session)

        response = await client.get(
            "/api/v1/admin/transactions?search=08110000001", headers=headers
        )
        assert response.status_code == 200
        assert response.json()["data"]["totalRecords"] == 3

    async def test_list_transactions_requires_auth(self, client):
        response = await client.get("/api/v1/admin/transactions")
        assert response.status_code == 401

    async def test_transaction_detail_returns_full_record(
        self, client, db_session, admin_payload
    ):
        headers = await _register_and_login(client, admin_payload)
        await _seed_user_and_transactions(db_session)

        listing = await client.get("/api/v1/admin/transactions", headers=headers)
        reference = listing.json()["data"]["records"][0]["reference"]

        response = await client.get(
            f"/api/v1/admin/transactions/{reference}", headers=headers
        )
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["reference"] == reference
        assert "audit_trail" in data
        assert "ledger_entries" in data

    async def test_transaction_detail_404_for_unknown_reference(self, client, admin_payload):
        headers = await _register_and_login(client, admin_payload)
        response = await client.get(
            "/api/v1/admin/transactions/does-not-exist", headers=headers
        )
        assert response.status_code == 404
