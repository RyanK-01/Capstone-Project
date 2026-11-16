import os

from sqlalchemy import MetaData, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DB_URL = os.getenv("DATABASE_URL")
if not DB_URL:
    raise RuntimeError(
        "DATABASE_URL is not set. Copy .env.example to .env and export it, "
        "or run the stack with docker compose."
    )

# Names every constraint deterministically so Alembic can alter/drop them later.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

engine = create_engine(DB_URL, pool_pre_ping=True, pool_size=20, max_overflow=30, connect_args={"connect_timeout": 10})
LocalSession = sessionmaker(autoflush=False, bind=engine)
Base = declarative_base(metadata=MetaData(naming_convention=NAMING_CONVENTION))


def get_db():
    db = LocalSession()
    try:
        yield db
    finally:
        db.close()
