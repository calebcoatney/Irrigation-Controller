from sqlmodel import create_engine, Session, SQLModel, select
from models import ZoneConfig, Schedule

DATABASE_URL = "sqlite:////data/irrigation.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})


def get_session():
    with Session(engine) as session:
        yield session


def init_db():
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for zone_id, name in [(1, "Front Yard"), (2, "Back Yard")]:
            if not session.get(ZoneConfig, zone_id):
                session.add(ZoneConfig(zone_id=zone_id, name=name))
                session.add(Schedule(zone_id=zone_id))
        session.commit()
