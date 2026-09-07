"""Cross-database column types for both PostgreSQL and SQLite."""

import uuid
from sqlalchemy import String, TypeDecorator, JSON as SqlJSON
from sqlalchemy.dialects.postgresql import UUID as PgUUID


class GUID(TypeDecorator):
    """Platform-independent GUID/UUID type.
    Uses PostgreSQL's native UUID type, otherwise uses String(36).
    """
    impl = String(36)
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PgUUID(as_uuid=True))
        else:
            return dialect.type_descriptor(String(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        elif dialect.name == "postgresql":
            return str(value) if not isinstance(value, uuid.UUID) else value
        else:
            return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        elif isinstance(value, uuid.UUID):
            return value
        else:
            try:
                return uuid.UUID(str(value))
            except (ValueError, TypeError):
                return value


# Cross-database JSON
JSON = SqlJSON
UUID = GUID
