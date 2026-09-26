"""Which plan programs apply to a store."""
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .models import Program, Store


def programs_for_store(db: Session, store: Store) -> tuple[list[Program], list[Program]]:
    """Returns (matched, other_chain_programs). Division narrows the match when set."""
    progs = db.scalars(select(Program).options(selectinload(Program.promos))
                       .where(Program.chain == store.chain, Program.active.is_(True))
                       .order_by(Program.brand, Program.account)).all()
    div = (store.division or "").strip().lower()
    if not div:
        return list(progs), []
    matched, other = [], []
    for p in progs:
        acct = p.account.lower()
        if acct == store.chain.lower() or div in acct or acct in div:
            matched.append(p)
        else:
            other.append(p)
    return matched, other
