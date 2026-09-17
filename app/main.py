"""API Carnet de Dettes - FastAPI + SQLite.

Lancer :  uvicorn app.main:app --reload
Docs    :  http://127.0.0.1:8000/docs
UI      :  http://127.0.0.1:8000/
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import schemas
from app.database import get_db, init_db
from app.models import Contact, Debt, DebtStatus, Direction, Payment

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Carnet de Dettes",
    description="Suivi des prets et emprunts : contacts, dettes, remboursements.",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # prod : ["https://localhost", "capacitor://localhost"]
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---- Mappers ----
def contact_out(contact: Contact) -> schemas.ContactOut:
    totals = contact.totals()
    return schemas.ContactOut(
        id=contact.id,
        name=contact.name,
        phone=contact.phone,
        open_debts=sum(1 for d in contact.debts if not d.is_settled),
        balances=[
            schemas.CurrencyBalance(currency=cur, **vals)
            for cur, vals in sorted(totals.items())
            if vals["to_receive"] or vals["to_pay"]
        ],
    )


def debt_out(debt: Debt) -> schemas.DebtOut:
    return schemas.DebtOut(
        id=debt.id,
        contact_id=debt.contact_id,
        contact_name=debt.contact.name,
        direction=debt.direction,
        amount=debt.amount,
        currency=debt.currency,
        issued_on=debt.issued_on,
        due_date=debt.due_date,
        note=debt.note,
        paid_amount=debt.paid_amount,
        remaining=debt.remaining,
        status=debt.status,
        days_late=debt.days_late,
        payments=[schemas.PaymentOut.model_validate(p) for p in debt.payments],
    )


def get_contact_or_404(db: Session, contact_id: int) -> Contact:
    contact = db.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(404, "Contact introuvable")
    return contact


def get_debt_or_404(db: Session, debt_id: int) -> Debt:
    debt = db.get(Debt, debt_id)
    if debt is None:
        raise HTTPException(404, "Dette introuvable")
    return debt


# ---- Contacts ----
@app.get("/api/contacts", response_model=list[schemas.ContactOut], tags=["Contacts"])
def list_contacts(
    q: str | None = Query(default=None, description="Recherche nom / telephone"),
    db: Session = Depends(get_db),
):
    stmt = select(Contact).order_by(Contact.name)
    if q:
        like = f"%{q.strip()}%"
        stmt = stmt.where(Contact.name.ilike(like) | Contact.phone.ilike(like))
    return [contact_out(c) for c in db.scalars(stmt).unique()]


@app.post(
    "/api/contacts",
    response_model=schemas.ContactOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Contacts"],
)
def create_contact(payload: schemas.ContactCreate, db: Session = Depends(get_db)):
    exists = db.scalar(select(Contact).where(Contact.name == payload.name))
    if exists:
        raise HTTPException(409, "Un contact porte deja ce nom")
    contact = Contact(**payload.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact_out(contact)


@app.put("/api/contacts/{contact_id}", response_model=schemas.ContactOut, tags=["Contacts"])
def update_contact(
    contact_id: int, payload: schemas.ContactUpdate, db: Session = Depends(get_db)
):
    contact = get_contact_or_404(db, contact_id)
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return contact_out(contact)


@app.delete(
    "/api/contacts/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Contacts"],
)
def delete_contact(
    contact_id: int,
    force: bool = Query(False, description="Supprimer meme s'il reste des dettes ouvertes"),
    db: Session = Depends(get_db),
):
    contact = get_contact_or_404(db, contact_id)
    open_debts = [d for d in contact.debts if not d.is_settled]
    if open_debts and not force:
        raise HTTPException(
            409,
            f"{len(open_debts)} dette(s) non soldee(s). Relancez avec ?force=true pour confirmer.",
        )
    db.delete(contact)
    db.commit()


# ---- Dettes ----
@app.get("/api/debts", response_model=list[schemas.DebtOut], tags=["Dettes"])
def list_debts(
    contact_id: int | None = None,
    direction: Direction | None = None,
    debt_status: DebtStatus | None = Query(default=None, alias="status"),
    currency: str | None = None,
    db: Session = Depends(get_db),
):
    stmt = select(Debt).order_by(Debt.due_date.is_(None), Debt.due_date, Debt.issued_on.desc())
    if contact_id:
        stmt = stmt.where(Debt.contact_id == contact_id)
    if direction:
        stmt = stmt.where(Debt.direction == direction)
    if currency:
        stmt = stmt.where(Debt.currency == currency.upper())
    debts = list(db.scalars(stmt).unique())
    if debt_status:
        debts = [d for d in debts if d.status is debt_status]
    return [debt_out(d) for d in debts]


@app.post(
    "/api/debts",
    response_model=schemas.DebtOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Dettes"],
)
def create_debt(payload: schemas.DebtCreate, db: Session = Depends(get_db)):
    get_contact_or_404(db, payload.contact_id)
    if payload.due_date and payload.due_date < payload.issued_on:
        raise HTTPException(422, "L'echeance ne peut pas preceder la date de la dette")
    debt = Debt(**payload.model_dump())
    db.add(debt)
    db.commit()
    db.refresh(debt)
    return debt_out(debt)


@app.put("/api/debts/{debt_id}", response_model=schemas.DebtOut, tags=["Dettes"])
def update_debt(debt_id: int, payload: schemas.DebtUpdate, db: Session = Depends(get_db)):
    debt = get_debt_or_404(db, debt_id)
    data = payload.model_dump(exclude_unset=True)
    if "currency" in data and data["currency"]:
        data["currency"] = data["currency"].upper()
    if "amount" in data and data["amount"] is not None and data["amount"] < debt.paid_amount:
        raise HTTPException(
            422, f"Montant inferieur aux remboursements deja enregistres ({debt.paid_amount})"
        )
    for field, value in data.items():
        setattr(debt, field, value)
    db.commit()
    db.refresh(debt)
    return debt_out(debt)


@app.delete("/api/debts/{debt_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["Dettes"])
def delete_debt(debt_id: int, db: Session = Depends(get_db)):
    db.delete(get_debt_or_404(db, debt_id))
    db.commit()


# ---- Remboursements ----
@app.post(
    "/api/debts/{debt_id}/payments",
    response_model=schemas.DebtOut,
    status_code=status.HTTP_201_CREATED,
    tags=["Remboursements"],
)
def add_payment(
    debt_id: int, payload: schemas.PaymentCreate, db: Session = Depends(get_db)
):
    debt = get_debt_or_404(db, debt_id)
    if debt.is_settled:
        raise HTTPException(409, "Cette dette est deja soldee")
    if payload.amount - debt.remaining > 0.005:
        raise HTTPException(
            422,
            f"Le reglement depasse le solde restant ({debt.remaining} {debt.currency})",
        )
    db.add(Payment(debt_id=debt.id, **payload.model_dump()))
    db.commit()
    db.refresh(debt)
    return debt_out(debt)


@app.post(
    "/api/debts/{debt_id}/settle",
    response_model=schemas.DebtOut,
    tags=["Remboursements"],
)
def settle_debt(debt_id: int, db: Session = Depends(get_db)):
    """Raccourci : solder la dette en un seul reglement du montant restant."""
    debt = get_debt_or_404(db, debt_id)
    if debt.is_settled:
        raise HTTPException(409, "Cette dette est deja soldee")
    db.add(Payment(debt_id=debt.id, amount=debt.remaining))
    db.commit()
    db.refresh(debt)
    return debt_out(debt)


@app.delete(
    "/api/payments/{payment_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["Remboursements"],
)
def delete_payment(payment_id: int, db: Session = Depends(get_db)):
    payment = db.get(Payment, payment_id)
    if payment is None:
        raise HTTPException(404, "Reglement introuvable")
    db.delete(payment)
    db.commit()


# ---- Resume ----
@app.get("/api/summary", response_model=list[schemas.SummaryOut], tags=["Resume"])
def summary(db: Session = Depends(get_db)):
    """Totaux a percevoir / a payer, groupes par devise (jamais additionnees)."""
    buckets: dict[str, dict[str, float]] = {}
    for debt in db.scalars(select(Debt)).unique():
        b = buckets.setdefault(
            debt.currency,
            {"to_receive": 0.0, "to_pay": 0.0, "overdue_count": 0, "overdue_amount": 0.0},
        )
        rest = debt.remaining
        if rest <= 0.005:
            continue
        if debt.direction is Direction.LENT:
            b["to_receive"] += rest
        else:
            b["to_pay"] += rest
        if debt.status is DebtStatus.OVERDUE:
            b["overdue_count"] += 1
            b["overdue_amount"] += rest
    return [
        schemas.SummaryOut(
            currency=cur,
            to_receive=round(b["to_receive"], 2),
            to_pay=round(b["to_pay"], 2),
            net=round(b["to_receive"] - b["to_pay"], 2),
            overdue_count=int(b["overdue_count"]),
            overdue_amount=round(b["overdue_amount"], 2),
        )
        for cur, b in sorted(buckets.items())
    ]


@app.get("/api/health", tags=["Resume"])
def health():
    return {"status": "ok"}


# ---- Frontend ----
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/", include_in_schema=False)
    def index():
        return FileResponse(STATIC_DIR / "index.html")
