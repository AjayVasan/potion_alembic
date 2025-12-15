import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool,text

from alembic.script import ScriptDirectory
from sqlalchemy.exc import ProgrammingError
from psycopg2.errors import UndefinedTable

from alembic import context

from models.tenant import Base

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = Base.metadata

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    def migration_per_tenant(current_tenant):
        with connectable.connect() as connection:
            if str(current_tenant).endswith("_schema"):
                connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{current_tenant}"'))
                connection.execute(text(f'SET search_path TO "{current_tenant}"'))
                connection.commit()
            else:
                print(f"Applying 1st Migration for {current_tenant}")
                connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{current_tenant}_schema"'))
                connection.execute(text(f'SET search_path TO "{current_tenant}_schema"'))
                connection.commit()
                

            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                version_table_schema=f"{current_tenant}_schema"
                                        if not str(current_tenant).endswith("_schema")
                                        else f"{current_tenant}",
                include_schemas=False,
            )

            with context.begin_transaction():
                context.run_migrations()
    def populate_meta(org_id:str , org_name:str):

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
            connection.execute(
                upsert_query,
                    {
                        "org_id": f"{org_id}",
                        "org_name": f"{org_name}",
                        "schema_name": f"{org_name}_schema"
                                        if not str(org_name).endswith("_schema")
                                        else f"{org_name}",
                        "plan_type": "basic",
                        "is_active": True,
                        "has_schema": True
                    }
                
            )
            connection.commit()

    """
    some really important shit
    """


    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    current_tenant = context.get_x_argument(as_dictionary=True).get("tenant")

    if str(current_tenant) != "all_orgs_" and str(current_tenant) != "0":
        if "/" in current_tenant:
            l = current_tenant.split(("/"))
            if len(l)==2:
                id,org_name = l[0],l[-1]
                migration_per_tenant(org_name)
                populate_meta(id,org_name)
            else:
                print("Error Entry Format <id>/<org_name>")
        # 
        else:
            # 1. Normalize the schema name
            target_schema = current_tenant
            if not target_schema.endswith("_schema"):
                target_schema = f"{target_schema}_schema"

            with connectable.connect() as connection:
                connection.execute(text(f'SET search_path TO public'))
                
                # 2. CHECK if tenant exists to get the REAL ID
                # This prevents the UniqueViolation on schema_name
                check_sql = text("SELECT org_id FROM public.tenants WHERE schema_name = :s")
                existing_id = connection.execute(check_sql, {"s": target_schema}).scalar()
                
                if existing_id:
                    # Use the ID that is already in the database
                    real_org_id = existing_id
                    print(f"Updating existing tenant: {real_org_id}")
                else:
                    # Only generate a new ID if it truly doesn't exist
                    res = connection.execute(text("SELECT id FROM tenants ORDER BY created_at DESC LIMIT 1"))
                    last_id = res.scalar() or 0
                    real_org_id = f"{current_tenant}{last_id}"
                    print(f"Creating new tenant: {real_org_id}")

            # 3. Migrate and Update Metadata using the CORRECT ID
            migration_per_tenant(current_tenant)
            populate_meta(real_org_id, current_tenant)


    elif str(current_tenant) == "all_orgs_" and str(current_tenant) != "0":
        with connectable.connect() as connection:
            connection.execute(text(f'SET search_path TO public'))
            result = connection.execute(text(f"select org_id, schema_name from tenants where has_schema = false order by created_at ASC"))
            rows = result.all()
            org_ids = [row.org_id for row in rows]
            schema_names = [row.schema_name for row in rows]
            if len(org_ids) == len(schema_names):
                for i in range(len(org_ids)):
                    migration_per_tenant(schema_names[i])
                    populate_meta(org_ids[i],schema_names[i])
    
    
    else:
        if str(current_tenant) == "0":
            with connectable.connect() as connection:
                connection.execute(text(f'SET search_path TO public'))
                result = connection.execute(text(f"select org_id, schema_name from tenants"))
                rows = result.all()
                org_ids = [row.org_id for row in rows]
                schema_names = [row.schema_name for row in rows]
                if len(org_ids) == len(schema_names):
                    for i in range(len(org_ids)):
                        if not str(schema_names[i]).endswith("_schema"):
                            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{current_tenant}_schema"'))
                            connection.execute(text(f'SET search_path TO "{schema_names[i]}_schema"'))
                        else:
                            connection.execute(text(f'SET search_path TO "{schema_names[i]}"'))
                        try:
                            alembic_result = connection.execute(text(f"select version_num from alembic_version"))
                            tenant_alembic_version = alembic_result.all()
                            script = ScriptDirectory.from_config(config)
                            head_revision = script.get_current_head()
                            if tenant_alembic_version != head_revision:
                                migration_per_tenant(schema_names[i])
                                populate_meta(org_ids[i],schema_names[i])
                        except ProgrammingError as e:
                            if isinstance(e.orig, UndefinedTable):
                                print(f"Found a new entry appling migrations for that too org_schema_name:{schema_names[i]}, org_id: {org_ids[i]}")
                                migration_per_tenant(schema_names[i])
                                populate_meta(org_ids[i],schema_names[i])
                            else:
                                print(e)

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
