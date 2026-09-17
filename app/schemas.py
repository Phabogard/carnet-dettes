"""Schemas Pydantic v2 : validation entree / serialisation sortie."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import DebtStatus, Direction

CURRENCIES = {"USD", "CDF", "EUR", "XAF", "XOF"}


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --------------------------------------------------------------------- Contact
class ContactBase(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=40)

    @field_validator("name", "phone")
    @classmethod
    def _strip(cls, v: str | None) -> str | None:
        return v.strip() if isinstance(v, str) else v


class ContactCreate(ContactBase):
    pass


class ContactUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    phone: str | None = Field(default=None, max_length=40)


class CurrencyBalance(BaseModel):
    currency: str
    to_receive: float
    to_pay: float
    net: float


class ContactOut(ORMModel, ContactBase):
    id: int
    balances: list[CurrencyBalance] = []
    open_debts: int = 0


# ------------------------------------------------------------------ Paiements
class PaymentCreate(BaseModel):
    amount: float = Field(gt=0)
    paid_on: date = Field(default_factory=date.today)
    note: str | None = None


class PaymentOut(ORMModel):
    id: int
    debt_id: int
    amount: float
    paid_on: date
    note: str | None = None


# ---------------------------------------------------------------------- Dettes
class DebtBase(BaseModel):
    contact_id: int
    direction: Direction
    amount: float = Field(gt=0, description="Montant initial de la dette")
    currency: str = "USD"
    issued_on: date = Field(default_factory=date.today)
    due_date: date | None = None
    note: str | None = None

    @field_validator("currency")
    @classmethod
    def _known_currency(cls, v: str) -> str:
        v = v.strip().upper()
        if v not in CURRENCIES:
            raise ValueError(f"Devise non supportee. Choix : {sorted(CURRENCIES)}")
        return v


class DebtCreate(DebtBase):
    pass


class DebtUpdate(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    currency: str | None = None
    issued_on: date | None = None
    due_date: date | None = None
    note: str | None = None


class DebtOut(ORMModel):
    id: int
    contact_id: int
    contact_name: str
    direction: Direction
    amount: float
    currency: str
    issued_on: date
    due_date: date | None = None
    note: str | None = None
    paid_amount: float
    remaining: float
    status: DebtStatus
    days_late: int
    payments: list[PaymentOut] = []


# --------------------------------------------------------------------- Resume
class SummaryOut(BaseModel):
    currency: str
    to_receive: float
    to_pay: float
    net: float
    overdue_count: int
    overdue_amount: int | float
