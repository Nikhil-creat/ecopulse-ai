from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base. Hypertables/indexes are created by infra/db/init/02_schema.sql;
    these models mirror that schema for typed access (and Alembic autogenerate checks)."""
