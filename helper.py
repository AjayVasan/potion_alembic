import re
from datetime import datetime
from sqlalchemy import text
from sqlalchemy.engine import Connection
from alembic import context

def get_create_date(revision):
    doc = revision.module.__doc__ or ""
    match = re.search(r"Create Date:\s*(.*)", doc)
    if not match:
        return None
    return datetime.fromisoformat(match.group(1).strip())


def log_system_audit(connection: Connection, action: str, org_id: str = None, details: str = None ,time: datetime = None):
    """
    Robustly inserts an entry into public.system_audit_log.
    """
    if time == None:
        time = datetime.now()
    try:
        # We explicitly use public.system_audit_log to bypass search_path issues
        stmt = text("""
            INSERT INTO public.system_audit_log (org_id, action, actor, details, created_at)
            VALUES (:org_id, :action, 'alembic_system', :details, :time)
        """)
        connection.execute(stmt, {
            "org_id": org_id,
            "action": action,
            "details": details or "{}",
            "time":time
        })
        # Note: We do NOT commit here if we want it to be part of the main transaction.
        # However, for audit logs, sometimes we want them even if the main tx fails.
        # But 'connection' here is often the one inside the migration transaction.
    except Exception as e:
        print(f"WARNING: Failed to write system audit log: {e}")

def record_migration_history(ctx, step, heads, run_args):
    """
    Callback for on_version_apply.
    """
    connection = ctx.connection
    
    org_id = run_args.get("tenant_id", "unknown_context")
    
    revision_id = step.up_revision_id if step.is_upgrade else step.down_revision_id
    migration_name = "unknown"
    
    try:
        script = context.script
        if script:
            rev = script.get_revision(revision_id)
            if rev:
                migration_name = rev.doc or "No message"
    except Exception:
        migration_name = "unavailable"

    try:
        stmt = text("""
            INSERT INTO public.tenant_migration_history 
            (org_id, migration_version, migration_name, applied_at, status, applied_by)
            VALUES (:org_id, :ver, :name, NOW(), :status, 'alembic_runner')
        """)
        
        connection.execute(stmt, {
            "org_id": org_id,
            "ver": revision_id,
            "name": migration_name,
            "status": "success"
        })
        
        log_system_audit(connection, f"MIGRATION_STEP_{revision_id}", org_id, f"Applied {migration_name}")
        
    except Exception as e:
        print(f"CRITICAL: Failed to write migration history for {org_id}: {e}")
        raise e