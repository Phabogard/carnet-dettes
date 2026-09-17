"""Modeles SQLAlchemy : Contact, Debt, Payment."""
from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

EPSILON = 0.005  # tolerance d'arrondi sur les montants


class Direction(str, enum.Enum):
    """Sens de la dette, vu depuis l'utilisateur."""

    LENT = "lent"          # J'ai prete -> on me doit
    BORROWED = "borrowed"  # J'ai emprunte -> je dois


class DebtStatus(str, enum.Enum):
    UNPAID = "unpaid"    # rien rembourse
    PARTIAL = "partial"  # partiellement rembourse
    PAID = "paid"        # solde
    OVERDUE = "overdue"  # echeance depassee et solde restant


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Contact(Base):
    __tablename__ = "contacts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    phone: Mapped[str | None] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    debts: Mapped[list["Debt"]] = relationship(
        back_populates="contact",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    # --- Soldes calcules -------------------------------------------------
    def totals(self) -> dict[str, dict[str, float]]:
        """Solde par devise : {'USD': {'to_receive': x, 'to_pay': y, 'net': z}}."""
        out: dict[str, dict[str, float]] = {}
        for debt in self.debts:
            bucket = out.setdefault(
                debt.currency, {"to_receive": 0.0, "to_pay": 0.0, "net": 0.0}
            )
            rest = debt.remaining
            if rest <= EPSILON:
                continue
            if debt.direction is Direction.LENT:
                bucket["to_receive"] += rest
            else:
                bucket["to_pay"] += rest
        for bucket in out.values():
            bucket["to_receive"] = round(bucket["to_receive"], 2)
            bucket["to_pay"] = round(bucket["to_pay"], 2)
            bucket["net"] = round(bucket["to_receive"] - bucket["to_pay"], 2)
        return out


class Debt(Base):
    __tablename__ = "debts"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_debt_amount_positive"),
        Index("ix_debts_contact_direction", "contact_id", "direction"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    direction: Mapped[Direction] = mapped_column(
        Enum(Direction, native_enum=False), nullable=False
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    currency: Mapped[str] = mapped_column(String(8), nullable=False, default="USD")
    issued_on: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    due_date: Mapped[date | None] = mapped_column(Date)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    contact: Mapped[Contact] = relationship(back_populates="debts", lazy="joined")
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="debt",
        cascade="all, delete-orphan",
        order_by="Payment.paid_on",
        lazy="selectin",
    )

    # --- Champs derives --------------------------------------------------
    @property
    def paid_amount(self) -> float:
        return round(sum(p.amount for p in self.payments), 2)

    @property
    def remaining(self) -> float:
        return round(self.amount - self.paid_amount, 2)

    @property
    def is_settled(self) -> bool:
        return self.remaining <= EPSILON

    @property
    def status(self) -> DebtStatus:
        if self.is_settled:
            return DebtStatus.PAID
        if self.due_date and self.due_date < date.today():
            return DebtStatus.OVERDUE
        if self.paid_amount > EPSILON:
            return DebtStatus.PARTIAL
        return DebtStatus.UNPAID

    @property
    def days_late(self) -> int:
        if self.status is not DebtStatus.OVERDUE or self.due_date is None:
            return 0
        return (date.today() - self.due_date).days


class Payment(Base):
    __tablename__ = "payments"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payment_amount_positive"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    debt_id: Mapped[int] = mapped_column(
        ForeignKey("debts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    paid_on: Mapped[date] = mapped_column(Date, nullable=False, default=date.today)
    note: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=_utcnow)

    debt: Mapped[Debt] = relationship(back_populates="payments")
