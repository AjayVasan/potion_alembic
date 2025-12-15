"""Minimal models for multi-tenant system focused on performance."""

from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Index, Integer, String, Text, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


# Public schema models (tenant metadata)
class Tenant(Base):
    """Tenant metadata stored in public schema."""

    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(String(50), unique=True, nullable=False, index=True)
    org_name = Column(String(255), nullable=False)
    schema_name = Column(String(63), unique=True, nullable=False, index=True)
    plan_type = Column(String(50), default="standard")  # free, standard, enterprise
    is_active = Column(Boolean, default=True, index=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    deleted_at = Column(DateTime(timezone=True), nullable=True)  # Soft delete
    has_schema = Column(Boolean,index=True,server_default=text("false"))
    test_public_meta_product = Column(String(1),nullable=True)


    __table_args__ = (
        Index("idx_tenant_active_schema", "is_active", "schema_name"),
        Index("idx_tenant_org_lookup", "org_id", "is_active"),
    )

    def __repr__(self) -> str:
        """Return a helpful string representation of the tenant."""
        return f"Tenant({self.org_id}: {self.org_name})"

    def __str__(self) -> str:
        """Return a user-friendly string representation."""
        return f"{self.org_id}: {self.org_name}"


class TenantMigrationHistory(Base):
    """Migration tracking per tenant."""

    __tablename__ = "tenant_migration_history"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(String(50), nullable=False, index=True)
    migration_version = Column(String(50), nullable=False)
    migration_name = Column(String(255), nullable=False)
    applied_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(20), default="success")  # success, failed, pending
    error_message = Column(Text, nullable=True)
    applied_by = Column(String(100), default="system")
    test_public_meta_product = Column(String(1),nullable=True)


    def __repr__(self) -> str:
        """Return a helpful string representation of the migration history."""
        return f"Migration({self.org_id}: {self.migration_version})"

    def __str__(self) -> str:
        """Return a user-friendly string representation."""
        return f"Migration {self.migration_version} for {self.org_id}"


class SystemAuditLog(Base):
    """Comprehensive audit logging for compliance."""

    __tablename__ = "system_audit_log"

    id = Column(Integer, primary_key=True, index=True)
    org_id = Column(String(50), nullable=True, index=True)  # NULL for system events
    action = Column(String(100), nullable=False, index=True)
    actor = Column(String(255), nullable=False)  # system, admin:user_id, api_key:abc
    details = Column(Text, nullable=True)  # JSON string with context
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    __table_args__ = (
        Index("idx_audit_org_time", "org_id", "created_at"),
        Index("idx_audit_action_time", "action", "created_at"),
    )

    def __repr__(self) -> str:
        """Return a helpful string representation of the audit log."""
        return f"Audit({self.action}: {self.org_id or 'system'})"

    def __str__(self) -> str:
        """Return a user-friendly string representation."""
        return f"Audit {self.action} on {self.org_id or 'system'}"

class AlembicVersion(Base):
    __tablename__ = "alembic_version"
    version_num = Column(String(32), primary_key=True,index=True)

# Note: Application-specific models (like User) should be defined
# in the application layer, not in the multi-tenant framework.
# The framework provides schema isolation and connection pooling,
# while applications define their own models per tenant schema.
