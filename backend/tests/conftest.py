import pytest
from sqlmodel import create_engine, Session, SQLModel
from models import ZoneConfig, Schedule


@pytest.fixture(name="engine")
def engine_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    return engine


@pytest.fixture(name="session")
def session_fixture(engine):
    with Session(engine) as session:
        yield session


@pytest.fixture(name="seeded_engine")
def seeded_engine_fixture():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        for zone_id, name in [(1, "Front Yard"), (2, "Back Yard")]:
            session.add(ZoneConfig(zone_id=zone_id, name=name, lat=40.0, lng=-105.0))
            session.add(Schedule(zone_id=zone_id))
        session.commit()
    return engine
