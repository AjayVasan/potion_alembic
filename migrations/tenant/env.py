import os
import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "../..")))

from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool,text

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
            connection.execute(text(f'CREATE SCHEMA IF NOT EXISTS "{current_tenant}_schema"'))
            connection.execute(text(f'SET search_path TO "{current_tenant}_schema"'))
            connection.commit()

            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                version_table_schema=f"{current_tenant}_schema",
                include_schemas=False,
            )

            with context.begin_transaction():
                context.run_migrations()
    def populate_meta(org_id:int , org_name:str):
        with connectable.connect() as connection:
            connection.execute(text(f'SET search_path TO public'))
            connection.execute(
                text("""
                    INSERT INTO public.tenants 
                    (org_id, org_name, schema_name, plan_type, is_active)
                    VALUES 
                    (:org_id, :org_name, :schema_name, :plan_type, :is_active)
                """),
                {
                    "org_id": f"{org_id}",
                    "org_name": f"{org_name}",
                    "schema_name": f"{org_name}_schema",
                    "plan_type": "basic",
                    "is_active": True
                }
            )

    """
    some really fucking important shit
    """


    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    current_tenant = context.get_x_argument(as_dictionary=True).get("tenant")

    if str(current_tenant) != "all_orgs_":
        migration_per_tenant(current_tenant)
    else:
        for i in ["ajay_dev/01","ajay_dev_2/02","ajay_nitroo/03"]: #DB Public.Tenants(tenant meta data )

            migration_per_tenant(i.split("/")[0])
            populate_meta(int(i.split("/")[1]),i.split("/")[0])


    

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
