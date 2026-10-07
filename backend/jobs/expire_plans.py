"""Rétrograde en base les abonnements pro/business dont plan_expires_at est
dépassé. Exécuté en tâche périodique hors cycle de requête (service Cron
Railway dédié) — jamais par le serveur web ni par un handler de requête.
"""
import sys

from sqlalchemy import text

from backend.database import SessionLocal

DOWNGRADE_SQL = text("""
    UPDATE users
    SET plan = 'free',
        subscription_status = 'expired'
    WHERE plan IN ('pro', 'business')
      AND plan_expires_at IS NOT NULL
      AND plan_expires_at < now()
    RETURNING id, email, plan_expires_at
""")


def run() -> int:
    db = SessionLocal()
    try:
        rows = db.execute(DOWNGRADE_SQL).fetchall()
        db.commit()
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()

    for row in rows:
        print(
            f"[expire_plans] downgrade -> free : id={row.id} email={row.email} "
            f"plan_expires_at={row.plan_expires_at}"
        )
    print(f"[expire_plans] {len(rows)} compte(s) rétrogradé(s)")
    return len(rows)


if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        print(f"[expire_plans] ERREUR: {e!r}")
        sys.exit(1)
