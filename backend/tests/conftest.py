import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app import models  # noqa: F401  (Base.metadata에 테이블 등록)
from app.config import settings
from app.db import Base, get_db
from app.main import app

# 테스트는 개발/시드용 DB(settings.database_url)와 절대 같은 DB를 쓰지 않는다.
# 과거에 같은 DB를 썼다가 테스트 fixture의 drop_all이 실제 개발 DB 스키마를
# 통째로 지워버린 적이 있어(마이그레이션으로 만든 테이블이 전부 삭제됨), 반드시
# "<원래 DB이름>_test"라는 별도 DB를 만들어 그 안에서만 생성/정리한다.
_base_url = make_url(settings.database_url)
_test_db_name = f"{_base_url.database or 'literec'}_test"
_test_url = _base_url.set(database=_test_db_name)


def _ensure_test_database_exists() -> None:
    admin_engine = create_engine(_base_url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    try:
        with admin_engine.connect() as conn:
            exists = conn.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"),
                {"name": _test_db_name},
            ).scalar()
            if not exists:
                conn.execute(text(f'CREATE DATABASE "{_test_db_name}"'))
    finally:
        admin_engine.dispose()


_ensure_test_database_exists()
_test_engine = create_engine(_test_url)
Base.metadata.create_all(_test_engine)
_TestSessionLocal = sessionmaker(bind=_test_engine, autoflush=False, autocommit=False)


@pytest.fixture()
def db_session():
    session = _TestSessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
        # 스키마는 유지하고 데이터만 비워 다음 테스트에 영향이 없도록 한다.
        with _test_engine.begin() as conn:
            table_names = ", ".join(f'"{t.name}"' for t in Base.metadata.sorted_tables)
            conn.execute(text(f"TRUNCATE TABLE {table_names} RESTART IDENTITY CASCADE"))


@pytest.fixture()
def client(db_session):
    def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
