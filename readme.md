# Project Change Summary & Documentation

This document provides a comprehensive summary of all changes from previous commits, including detailed migration information, usage examples, and implementation details.

---

## 📋 Table of Contents

1. [Overview of Changes](#overview-of-changes)
2. [Detailed Migration Changes](#detailed-migration-changes)
3. [Database Schema Evolution](#database-schema-evolution)
4. [Multi-Tenancy Implementation](#multi-tenancy-implementation)
5. [Usage Examples & Commands](#usage-examples--commands)
6. [Migration Guide](#migration-guide)

---

## Overview of Changes

### Summary
From commit `0a15b7c` (table population pending) to the current state, significant changes have been made to support a robust multi-tenant architecture with PostgreSQL schemas. The changes focus on:

- **Alembic configuration improvements** for better schema tracking
- **Three new public schema migrations** to manage tenant metadata
- **Enhanced tenant migration script** with advanced migration control logic
- **Database model updates** to reflect new schema columns
- **Template improvements** for future migration templates

### Changed Files
- `migrations/public/env.py` - Added `compare_server_default=True` configuration
- `migrations/public/versions/` - Three new migration files added
- `migrations/tenant/env.py` - Major rewrite with improved migration logic
- `migrations/tenant/script.py.mako` - Added `check()` function definition
- `models/public.py` - Added `has_schema` column to Tenant model

---

## Detailed Migration Changes

### Public Schema Migrations

#### Migration 1: `0a947917dca0_public_testing_01.py`
**Date**: 2025-12-15 11:36:30  
**Revision ID**: `0a947917dca0`  
**Previous Revision**: `f64aba2f71e7`

**Purpose**: Initial testing migration to add a temporary column for testing purposes.

**Changes**:
- Added column `test_public_meta_product` (String(1)) to the `tenants` table

**Upgrade Command**:
```sql
ALTER TABLE tenants ADD COLUMN test_public_meta_product VARCHAR(1);
```

**Downgrade Command**:
```sql
ALTER TABLE tenants DROP COLUMN test_public_meta_product;
```

---

#### Migration 2: `46616bfc39e7_public_testing_02.py`
**Date**: 2025-12-15 11:42:38  
**Revision ID**: `46616bfc39e7`  
**Previous Revision**: `0a947917dca0`

**Purpose**: Replace temporary test column with the actual `has_schema` boolean flag and create an index for performance.

**Changes**:
- Added column `has_schema` (Boolean) to the `tenants` table
- Created index `ix_tenants_has_schema` on the `has_schema` column
- Removed the temporary `test_public_meta_product` column

**Upgrade Operations**:
```python
op.add_column('tenants', sa.Column('has_schema', sa.Boolean(), nullable=True))
op.create_index(op.f('ix_tenants_has_schema'), 'tenants', ['has_schema'], unique=False)
op.drop_column('tenants', 'test_public_meta_product')
```

**Use Case**: The `has_schema` column tracks whether a tenant has been provisioned with a separate PostgreSQL schema.

---

#### Migration 3: `be9be28400f3_public_testing_03.py`
**Date**: 2025-12-15 13:53:21  
**Revision ID**: `be9be28400f3`  
**Previous Revision**: `46616bfc39e7`

**Purpose**: Set a server-side default value for the `has_schema` column to improve schema robustness.

**Changes**:
- Altered `has_schema` column to set `server_default=false`
- This ensures new tenant records default to having no schema without application intervention

**Upgrade Operations**:
```python
op.alter_column('tenants', 'has_schema',
           existing_type=sa.BOOLEAN(),
           server_default=sa.text('false'),
           existing_nullable=True)
```

**Benefit**: Server-side defaults are more reliable and provide database-level consistency.

---

## Database Schema Evolution

### Tenant Table Schema Changes

The `tenants` table in the `public` schema has evolved as follows:

**Before Changes** (Previous State):
```sql
CREATE TABLE public.tenants (
    id SERIAL PRIMARY KEY,
    org_id VARCHAR UNIQUE NOT NULL,
    org_name VARCHAR NOT NULL,
    schema_name VARCHAR NOT NULL,
    plan_type VARCHAR,
    is_active BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP NULL
);
```

**After Changes** (Current State):
```sql
CREATE TABLE public.tenants (
    id SERIAL PRIMARY KEY,
    org_id VARCHAR UNIQUE NOT NULL,
    org_name VARCHAR NOT NULL,
    schema_name VARCHAR NOT NULL,
    plan_type VARCHAR,
    is_active BOOLEAN,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP,
    deleted_at TIMESTAMP NULL,
    has_schema BOOLEAN DEFAULT false  -- NEW COLUMN
);

CREATE INDEX ix_tenants_has_schema ON tenants(has_schema);
```

### Configuration Changes

**File**: `migrations/public/env.py`

**Change**: Added `compare_server_default=True` to the Alembic context configuration.

```python
context.configure(
    connection=connection, 
    target_metadata=target_metadata,
    version_table_schema="public",
    compare_server_default=True  # NEW
)
```

**Impact**: This enables Alembic's autogenerate feature to detect and track changes in server-side default values, ensuring the migration script properly captures all schema modifications.

---

## Multi-Tenancy Implementation

### Tenant Migration Script Enhancements

**File**: `migrations/tenant/env.py`

The tenant migration script has been completely redesigned to support advanced multi-tenant operations.

#### New Imports
```python
from alembic.script import ScriptDirectory
from sqlalchemy.exc import ProgrammingError
from psycopg2.errors import UndefinedTable
```

These imports enable:
- Checking the current Alembic version
- Handling database errors gracefully
- Detecting undefined tables

#### Improved `migration_per_tenant()` Function

The function now handles both schema name formats:
- Tenants with schema suffix: `tenant_schema` (existing format)
- Tenants without suffix: `tenant` (new format)

```python
def migration_per_tenant(current_tenant):
    with connectable.connect() as connection:
        if current_tenant.endswith("_schema"):
            # Schema already has _schema suffix
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{current_tenant}"'))
            connection.execute(text(f'SET search_path TO "{current_tenant}"'))
        else:
            # Schema needs _schema suffix appended
            print(f"Applying 1st Migration for {current_tenant}")
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{current_tenant}_schema"'))
            connection.execute(text(f'SET search_path TO "{current_tenant}_schema"'))
        connection.commit()
        
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            version_table_schema=current_tenant_schema
        )
        
        with context.begin_transaction():
            context.run_migrations()
```

#### Redesigned `populate_meta()` Function

Now uses PostgreSQL's `INSERT ... ON CONFLICT` (upsert) pattern to handle both new and existing tenants:

```python
def populate_meta(org_id: str, org_name: str):
    upsert_query = text("""
        INSERT INTO public.tenants 
            (org_id, org_name, schema_name, plan_type, is_active, created_at, updated_at, has_schema)
        VALUES 
            (:org_id, :org_name, :schema_name, :plan_type, :is_active, NOW(), NOW(), :has_schema)
        ON CONFLICT (org_id) 
        DO UPDATE SET
            schema_name = EXCLUDED.schema_name,
            plan_type = EXCLUDED.plan_type,
            is_active = EXCLUDED.is_active,
            has_schema = EXCLUDED.has_schema,
            updated_at = NOW();
    """)
    
    with connectable.connect() as connection:
        connection.execute(text(f'SET search_path TO public'))
        connection.execute(upsert_query, {
            "org_id": f"{org_id}",
            "org_name": f"{org_name}",
            "schema_name": f"{org_name}_schema" if not org_name.endswith("_schema") else f"{org_name}",
            "plan_type": "basic",
            "is_active": True,
            "has_schema": True
        })
        connection.commit()
```

**Benefits**:
- Prevents duplicate key violations
- Updates existing tenant records with new information
- Tracks when `has_schema` is set to True

#### Advanced Migration Control Logic

The main migration execution block now supports multiple modes:

**Mode 1**: Single Tenant Migration with Format Support
```python
if str(current_tenant) != "all_orgs_" and str(current_tenant) != "0":
    if "/" in current_tenant:
        # Format: id/org_name
        l = current_tenant.split(("/"))
        if len(l) == 2:
            id, org_name = l[0], l[-1]
            migration_per_tenant(org_name)
            populate_meta(id, org_name)
    else:
        # Just tenant name, auto-fetch latest org_id
        with connectable.connect() as connection:
            connection.execute(text(f'SET search_path TO public'))
            result = connection.execute(text(f"SELECT id FROM tenants ORDER BY created_at DESC LIMIT 1;"))
            id = result.scalar()
            migration_per_tenant(current_tenant)
            populate_meta((current_tenant + str(id)), current_tenant)
```

**Mode 2**: Migrate Only Tenants Without Schema
```python
elif str(current_tenant) == "all_orgs_":
    with connectable.connect() as connection:
        connection.execute(text(f'SET search_path TO public'))
        result = connection.execute(text(f"select org_id, schema_name from tenants where has_schema = false order by created_at ASC"))
        rows = result.all()
        org_ids = [row.org_id for row in rows]
        schema_names = [row.schema_name for row in rows]
        
        if len(org_ids) == len(schema_names):
            for i in range(len(org_ids)):
                migration_per_tenant(schema_names[i])
                populate_meta(org_ids[i], schema_names[i])
```

**Mode 3**: Migrate All Tenants (Intelligent Update)
```python
elif str(current_tenant) == "0":
    with connectable.connect() as connection:
        connection.execute(text(f'SET search_path TO public'))
        result = connection.execute(text(f"select org_id, schema_name from tenants"))
        rows = result.all()
        
        for i in range(len(org_ids)):
            try:
                alembic_result = connection.execute(text(f"select version_num from alembic_version"))
                tenant_alembic_version = alembic_result.all()
                script = ScriptDirectory.from_config(config)
                head_revision = script.get_current_head()
                
                if tenant_alembic_version != head_revision:
                    # Only migrate if versions don't match
                    migration_per_tenant(schema_names[i])
                    populate_meta(org_ids[i], schema_names[i])
            except ProgrammingError as e:
                if isinstance(e.orig, UndefinedTable):
                    # New tenant, apply migrations
                    migration_per_tenant(schema_names[i])
                    populate_meta(org_ids[i], schema_names[i])
```

---

## Usage Examples & Commands

### Prerequisites

Ensure you have the following environment variables or database connection configured:
```bash
export DATABASE_URL="postgresql://user:password@localhost:5432/dbname"
```

### Example 1: Migrate a Single Tenant

**Scenario**: You have a new tenant organization named `acme_corp` with ID `101`.

**Command**:
```bash
alembic --name alembic:tenant -x tenant=101/acme_corp upgrade head
```

**What happens**:
1. Creates schema `acme_corp_schema` in PostgreSQL
2. Applies all pending migrations to the schema
3. Inserts/updates tenant metadata in `public.tenants` table
4. Sets `has_schema = true` for this tenant

### Example 2: Migrate Multiple Tenants (All without Schema)

**Scenario**: You have multiple tenants in the `public.tenants` table that haven't had schemas created yet (`has_schema = false`).

**Command**:
```bash
alembic --name alembic:tenant -x tenant=all_orgs_ upgrade head
```

**What happens**:
1. Queries `public.tenants` for all rows where `has_schema = false`
2. For each tenant:
   - Creates the PostgreSQL schema
   - Applies all migrations
   - Updates `has_schema = true`
3. Ordered by `created_at` (oldest first)

### Example 3: Migrate All Tenants (Check & Update)

**Scenario**: You want to ensure all existing tenants are at the latest migration version. This mode checks each tenant's current migration version against the head revision.

**Command**:
```bash
alembic --name alembic:tenant -x tenant=0 upgrade head
```

**What happens**:
1. Fetches all tenants from `public.tenants`
2. For each tenant:
   - Checks current Alembic version in that tenant's schema
   - Compares against the head revision
   - Only migrates if versions differ
   - Handles new tenants that have no `alembic_version` table
3. Prints diagnostic messages for each operation

### Example 4: Migrate Public Schema

The public schema contains shared tenant metadata and uses a separate Alembic configuration.

**Command**:
```bash
alembic --name alembic:public upgrade head
```

**What happens**:
1. Applies all pending migrations to the `public` schema
2. Updates the `tenants` table structure
3. Updates Alembic version tracking in `public.alembic_version`

### Example 5: Create and Apply a New Tenant Migration

**Scenario**: You need to add a new column to tenant schemas.

**Step 1**: Generate the migration auto-detected changes
```bash
alembic --name alembic:tenant revision --autogenerate -m "add_new_column_to_schema"
```

This creates a new migration file in `migrations/tenant/versions/`.

**Step 2**: Apply to a specific tenant for testing
```bash
alembic --name alembic:tenant -x tenant=test_tenant upgrade head
```

**Step 3**: Once verified, apply to all tenants
```bash
alembic --name alembic:tenant -x tenant=all_orgs_ upgrade head
```

### Example 6: Downgrade Operations

**Downgrade a single tenant to previous revision**:
```bash
alembic --name alembic:tenant -x tenant=acme_corp downgrade -1
```

**Downgrade all tenants**:
```bash
alembic --name alembic:tenant -x tenant=0 downgrade -1
```

### Example 7: Check Migration Status

**View current head revision**:
```bash
alembic --name alembic:tenant current
```

**View migration history**:
```bash
alembic --name alembic:tenant history
```

**View branches**:
```bash
alembic --name alembic:tenant branches
```

---

## Migration Guide

### For Database Administrators

#### Step-by-Step: Adding a New Tenant

**1. Add tenant to public.tenants table**:
```sql
INSERT INTO public.tenants (org_id, org_name, schema_name, plan_type, is_active, created_at, updated_at, has_schema)
VALUES ('123', 'new_company', 'new_company_schema', 'basic', true, NOW(), NOW(), false);
```

**2. Run tenant migration**:
```bash
alembic --name alembic:tenant -x tenant=123/new_company upgrade head
```

**3. Verify**:
```sql
-- Check if schema was created
\dn

-- Check if tenant metadata was updated
SELECT * FROM public.tenants WHERE org_id = '123';

-- Should show has_schema = true
```

#### Step-by-Step: Updating Public Schema

**1. Generate migration for public schema changes**:
```bash
alembic --name alembic:public revision --autogenerate -m "describe_your_change"
```

**2. Review the generated migration file** in `migrations/public/versions/`

**3. Apply the migration**:
```bash
alembic --name alembic:public upgrade head
```

**4. Apply to all tenants** (if applicable):
```bash
alembic --name alembic:tenant -x tenant=0 upgrade head
```

### Common Issues and Troubleshooting

**Issue**: Migration fails with "schema does not exist"
- **Solution**: Ensure the `migration_per_tenant()` function is creating the schema before running migrations

**Issue**: `has_schema` column not updated
- **Solution**: Check that `populate_meta()` is being called after `migration_per_tenant()`

**Issue**: Duplicate key violation in tenants table
- **Solution**: The upsert logic should handle this, but check for conflicting `org_id` values

**Issue**: Alembic version mismatch between tenants
- **Solution**: Use `tenant=0` mode to intelligently update only out-of-sync tenants

---

## Technical Summary

### Architecture
- **Public Schema**: Stores tenant metadata, uses standard Alembic configuration
- **Tenant Schemas**: One schema per tenant (e.g., `acme_corp_schema`), uses advanced Alembic script with multi-mode support
- **Metadata Tracking**: `has_schema` column indicates whether a tenant has been fully provisioned

### Key Features
✅ Multi-tenant schema isolation  
✅ Automatic schema creation  
✅ Intelligent migration tracking  
✅ Upsert-based metadata updates  
✅ Supports multiple tenant naming conventions  
✅ Graceful error handling for new tenants  
✅ Version checking before migration  

### Files Modified
- `migrations/public/env.py` (1 change)
- `migrations/public/versions/` (3 new files)
- `migrations/tenant/env.py` (complete rewrite)
- `migrations/tenant/script.py.mako` (1 addition)
- `models/public.py` (1 column addition)
