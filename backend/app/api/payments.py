"""Payments API — Cashfree payment gateway integration."""

from __future__ import annotations

import logging
from typing import Optional
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.deps import get_db
from app.models.models import Event, Participant
from app.schemas.schemas import (
    CreateOrderRequest,
    CreateOrderResponse,
    ParticipantOut,
    ReconcilePaymentRequest,
    ReconcilePaymentResponse,
    VerifyPaymentRequest,
    VerifyPaymentResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/payments", tags=["payments"])

CASHFREE_SANDBOX_URL = "https://sandbox.cashfree.com/pg"
CASHFREE_PROD_URL = "https://api.cashfree.com/pg"


def get_cashfree_config_for_event(event: Optional[Event] = None) -> tuple[str, str, str, str]:
    """Returns (app_id, secret_key, env, base_url) for a specific event or global settings."""
    app_id = (event.cashfree_app_id if event and event.cashfree_app_id else None) or settings.CASHFREE_APP_ID
    secret_key = (event.cashfree_secret_key if event and event.cashfree_secret_key else None) or settings.CASHFREE_SECRET_KEY
    env = (event.cashfree_env if event and event.cashfree_env else None) or settings.CASHFREE_ENV or "sandbox"
    base_url = CASHFREE_PROD_URL if env == "production" else CASHFREE_SANDBOX_URL
    return app_id, secret_key, env, base_url


async def resolve_event_for_order(order_id: str, db: AsyncSession) -> Optional[Event]:
    """Find the Event associated with an order_id."""
    # 1. Check if participant exists
    res = await db.execute(select(Participant).where(Participant.payment_order_id == order_id))
    p = res.scalar_one_or_none()
    if p and p.event_id:
        return await db.get(Event, p.event_id)

    # 2. Extract slug from GEEKAI_{SLUG}_{UUID}
    parts = order_id.split("_")
    if len(parts) >= 3 and parts[0] == "GEEKAI":
        slug_guess = "_".join(parts[1:-1]).lower()
        evt_res = await db.execute(select(Event).where(func.lower(Event.slug) == slug_guess))
        evt = evt_res.scalar_one_or_none()
        if evt:
            return evt

    return None


@router.post("/create-order", response_model=CreateOrderResponse)
async def create_order(body: CreateOrderRequest, db: AsyncSession = Depends(get_db)):
    event_res = await db.execute(select(Event).where(Event.slug == body.event_slug))
    event = event_res.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if not event.cashfree_enabled:
        raise HTTPException(status_code=400, detail="Cashfree payment is not enabled for this event")

    if event.registration_fee == 0:
        raise HTTPException(status_code=400, detail="Event registration is free; no payment required")

    app_id, secret_key, env, base_url = get_cashfree_config_for_event(event)
    if not app_id or not secret_key:
        raise HTTPException(status_code=503, detail="Payment gateway not configured for this event")

    order_id = f"GEEKAI_{body.event_slug.upper()}_{uuid.uuid4().hex[:8].upper()}"

    payload = {
        "order_id": order_id,
        "order_amount": body.amount / 100,  # Cashfree expects amount in rupees
        "order_currency": "INR",
        "customer_details": {
            "customer_id": f"CUST_{body.customer_email.replace('@', '_').replace('.', '_')}",
            "customer_email": body.customer_email,
            "customer_phone": body.customer_phone or "9999999999",
            "customer_name": body.customer_name,
        },
        "order_meta": {
            "notify_url": f"{settings.effective_backend_url}/api/payments/webhook",
        },
    }

    headers = {
        "Content-Type": "application/json",
        "x-api-version": "2023-08-01",
        "x-client-id": app_id,
        "x-client-secret": secret_key,
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{base_url}/orders", json=payload, headers=headers)

    if response.status_code not in (200, 201):
        logger.error(f"Cashfree order creation failed: {response.text}")
        raise HTTPException(status_code=502, detail="Payment gateway error")

    data = response.json()
    return CreateOrderResponse(
        order_id=order_id,
        payment_session_id=data.get("payment_session_id", ""),
        order_status=data.get("order_status", "ACTIVE"),
    )


@router.post("/verify", response_model=VerifyPaymentResponse)
async def verify_payment(body: VerifyPaymentRequest, db: AsyncSession = Depends(get_db)):
    """Verify Cashfree payment using order ID."""
    event = await resolve_event_for_order(body.order_id, db)
    app_id, secret_key, env, base_url = get_cashfree_config_for_event(event)

    if not app_id or not secret_key:
        raise HTTPException(status_code=503, detail="Payment gateway not configured")

    headers = {
        "x-api-version": "2023-08-01",
        "x-client-id": app_id,
        "x-client-secret": secret_key,
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(f"{base_url}/orders/{body.order_id}", headers=headers)

    if response.status_code != 200:
        raise HTTPException(status_code=502, detail="Could not verify payment")

    data = response.json()
    order_status = data.get("order_status", "")
    paid = order_status == "PAID"

    return VerifyPaymentResponse(
        order_id=body.order_id,
        order_status=order_status,
        paid=paid,
        amount=int((data.get("order_amount", 0)) * 100),  # convert back to paise
    )


async def check_cashfree_order_paid(
    order_id: str,
    db: Optional[AsyncSession] = None,
    event: Optional[Event] = None,
) -> tuple[bool, dict]:
    """Helper to check if a Cashfree order has been paid."""
    if not event and db:
        event = await resolve_event_for_order(order_id, db)
    app_id, secret_key, env, base_url = get_cashfree_config_for_event(event)

    if not app_id or not secret_key:
        return False, {}

    headers = {
        "x-api-version": "2023-08-01",
        "x-client-id": app_id,
        "x-client-secret": secret_key,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(f"{base_url}/orders/{order_id}", headers=headers)
        if response.status_code != 200:
            return False, {}
        data = response.json()
        return (data.get("order_status") == "PAID", data)
    except Exception as exc:
        logger.warning(f"Error checking Cashfree order {order_id}: {exc}")
        return False, {}


@router.post("/reconcile", response_model=ReconcilePaymentResponse)
async def reconcile_payment(
    body: ReconcilePaymentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reconcile a paid Cashfree order with an existing or pending participant."""
    paid, data = await check_cashfree_order_paid(body.order_id, db=db)
    if not paid:
        return ReconcilePaymentResponse(
            reconciled=False,
            message="Payment order has not been completed on Cashfree.",
            order_id=body.order_id,
            paid=False,
            participant=None,
        )

    # Order is PAID. Check if a participant is already linked to this order_id
    stmt = select(Participant).where(Participant.payment_order_id == body.order_id)
    res = await db.execute(stmt)
    p = res.scalar_one_or_none()

    if not p and body.email:
        stmt2 = select(Participant).where(Participant.email == body.email)
        res2 = await db.execute(stmt2)
        p = res2.scalar_one_or_none()

    if not p and data.get("customer_details", {}).get("customer_email"):
        cust_email = data["customer_details"]["customer_email"]
        stmt3 = select(Participant).where(Participant.email == cust_email)
        res3 = await db.execute(stmt3)
        p = res3.scalar_one_or_none()

    if p:
        p.payment_status = "SUCCESS"
        p.payment_order_id = body.order_id
        await db.commit()
        await db.refresh(p)
        return ReconcilePaymentResponse(
            reconciled=True,
            message="Participant payment successfully reconciled and confirmed.",
            order_id=body.order_id,
            paid=True,
            participant=ParticipantOut.model_validate(p),
        )

    return ReconcilePaymentResponse(
        reconciled=False,
        message="Order is paid, but participant details were not yet saved. You can complete registration with this Order ID without paying again.",
        order_id=body.order_id,
        paid=True,
        participant=None,
    )


@router.post("/webhook")
async def cashfree_webhook(request: dict):
    """Cashfree webhook for payment notifications."""
    logger.info(f"Cashfree webhook received: {request}")
    return {"status": "ok"}
