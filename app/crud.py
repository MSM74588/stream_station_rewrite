from sqlmodel import Session, select
from .models import Item

def get_items(session: Session):
    return session.exec(select(Item)).all()

def create_item(session: Session, item: Item):
    session.add(item)
    session.commit()
    session.refresh(item)
    return item
