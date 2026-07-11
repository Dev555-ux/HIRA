"""Customer mutation actions: manual create, update, delete (Sprint 37).

Reads (list/get/timeline) stay in app/api/customers.py, matching that
file's existing shape. This module exists for mutations specifically,
matching app/services/leads.py's convention: typed exceptions, tenant-
scoped via get_scoped, and race-safe against the DB's own uniqueness
constraint the same way Sprint 36 made create_lead/provision_business
race-safe.

Manually creating or updating a customer here must never create a Lead,
Conversation, or Message, and must never attempt a WhatsApp send — those
are exclusively driven by the WhatsApp webhook / AI orchestration pipeline
(app/webhooks/whatsapp.py, app/ai/*), which this module never touches.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.tenant import get_scoped
from app.models import Customer

logger = logging.getLogger(__name__)


class CustomerAlreadyExistsError(Exception):
    """A customer with this phone number already exists for this business."""


class CustomerNotFoundError(Exception):
    """The customer doesn't exist, or doesn't belong to this business."""


class MissingCustomerInfoError(Exception):
    """No customer_id/phone/email match was found, and no name was given to
    create a new customer."""


def _find_by_phone(db: Session, business_id: uuid.UUID, wa_phone: str) -> Customer | None:
    return db.scalars(
        select(Customer).where(Customer.business_id == business_id, Customer.wa_phone == wa_phone)
    ).first()


def _find_by_email(db: Session, business_id: uuid.UUID, email: str) -> Customer | None:
    return db.scalars(
        select(Customer).where(Customer.business_id == business_id, Customer.email == email)
    ).first()


def resolve_or_create_customer(
    db: Session,
    business_id: uuid.UUID,
    *,
    customer_id: uuid.UUID | None = None,
    wa_phone: str | None = None,
    email: str | None = None,
    display_name: str | None = None,
    company: str | None = None,
) -> Customer:
    """Find the customer a manually-created Lead should attach to, or create
    one (Sprint 38). Priority, matching the product spec exactly:

    1. `customer_id`, if given — must belong to this business.
    2. Else `wa_phone`, if given and it matches an existing customer.
    3. Else `email`, if given and it matches an existing customer.
    4. Else create a new customer from `display_name`/`company`/`wa_phone`/
       `email` — raises MissingCustomerInfoError if `display_name` is blank,
       since a new customer can't be created without a name.

    A match is reused as-is: none of the typed contact fields overwrite an
    existing customer's data as a side effect of creating a lead for them.

    Raises CustomerNotFoundError if `customer_id` doesn't belong to this
    business, or CustomerAlreadyExistsError (from create_customer) if a
    concurrent request wins a race on `wa_phone` between the lookup above
    and the insert.
    """
    if customer_id is not None:
        customer = get_scoped(db, Customer, business_id, customer_id)
        if customer is None:
            raise CustomerNotFoundError("Customer not found for this business")
        return customer

    if wa_phone:
        customer = _find_by_phone(db, business_id, wa_phone)
        if customer is not None:
            return customer

    if email:
        customer = _find_by_email(db, business_id, email)
        if customer is not None:
            return customer

    if not display_name or not display_name.strip():
        raise MissingCustomerInfoError("A name is required to create a new customer for this lead")

    return create_customer(
        db,
        business_id,
        display_name=display_name.strip(),
        wa_phone=wa_phone,
        email=email,
        company=company,
    )


def create_customer(
    db: Session,
    business_id: uuid.UUID,
    *,
    display_name: str,
    wa_phone: str | None = None,
    email: str | None = None,
    company: str | None = None,
    notes: str | None = None,
) -> Customer:
    """Manually add a customer. Raises CustomerAlreadyExistsError if
    `wa_phone` is given and already belongs to another customer of this
    business — the same UNIQUE(business_id, wa_phone) constraint the
    WhatsApp webhook's get-or-create relies on (app/webhooks/whatsapp.py).

    The upfront check below is inherently check-then-insert (same race as
    Sprint 36's create_lead/provision_business): the wrapped flush() is
    what actually prevents the duplicate if two requests race.
    """
    if wa_phone and _find_by_phone(db, business_id, wa_phone) is not None:
        raise CustomerAlreadyExistsError("A customer with this phone number already exists")

    customer = Customer(
        business_id=business_id,
        wa_phone=wa_phone,
        display_name=display_name,
        email=email,
        company=company,
        notes=notes,
    )
    db.add(customer)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise CustomerAlreadyExistsError(
            "A customer with this phone number already exists"
        ) from None
    db.commit()
    db.refresh(customer)
    logger.info("Manually created customer %s for business %s", customer.id, business_id)
    return customer


def update_customer(
    db: Session,
    business_id: uuid.UUID,
    customer_id: uuid.UUID,
    updates: dict[str, Any],
) -> Customer:
    """Partial update (only fields explicitly provided — see
    app/api/customers.py's `model_dump(exclude_unset=True)`). Raises
    CustomerNotFoundError, or CustomerAlreadyExistsError if changing
    wa_phone to one already used by another customer of this business.
    """
    customer = get_scoped(db, Customer, business_id, customer_id)
    if customer is None:
        raise CustomerNotFoundError("Customer not found for this business")

    if "wa_phone" in updates and updates["wa_phone"]:
        existing = _find_by_phone(db, business_id, updates["wa_phone"])
        if existing is not None and existing.id != customer.id:
            raise CustomerAlreadyExistsError("A customer with this phone number already exists")

    for field, value in updates.items():
        setattr(customer, field, value)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise CustomerAlreadyExistsError(
            "A customer with this phone number already exists"
        ) from None
    db.refresh(customer)
    logger.info("Updated customer %s (business %s): %s", customer_id, business_id, sorted(updates))
    return customer


def delete_customer(db: Session, business_id: uuid.UUID, customer_id: uuid.UUID) -> bool:
    """Delete a customer, tenant-scoped. Returns False if not found.

    Cascades to Conversations/Messages/Leads/Appointments (ON DELETE
    CASCADE), matching every other tenant-scoped delete in this codebase
    (e.g. delete_lead cascading to LeadEvent) — there is no soft-delete or
    history-preservation convention here to deviate from.
    """
    customer = get_scoped(db, Customer, business_id, customer_id)
    if customer is None:
        return False
    db.delete(customer)
    db.commit()
    logger.info("Deleted customer %s (business %s)", customer_id, business_id)
    return True
