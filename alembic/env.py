import os
from logging.config import fileConfig

from sqlalchemy import engine_from_config
from sqlalchemy import pool

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Import tous les modeles pour peupler Base.metadata (meme pattern que
# backend/database.py:get_db, qui importe explicitement les modeles avant
# toute operation de schema).
from backend.database import Base  # noqa: E402
import backend.models  # noqa: E402,F401

target_metadata = Base.metadata

# URL lue depuis DATABASE_URL (jamais commitee en dur dans alembic.ini),
# meme normalisation postgres:// -> postgresql:// que backend/database.py.
db_url = os.getenv("DATABASE_URL")
if db_url:
    db_url = db_url.replace("postgres://", "postgresql://", 1)
    config.set_main_option("sqlalchemy.url", db_url)

# Objets presents en base mais volontairement hors du perimetre ORM, ou
# declares au niveau modele sans jamais avoir ete appliques en prod
# (create_all() ne modifie jamais une table existante). Inventorie lors de
# l'audit du 2026-10-02 : ne pas y toucher ici, ce sont des ecarts connus a
# traiter via une migration deliberee future, pas via ce baseline.
IGNORED_TABLES = {"exchange_rates"}  # table brute, non mappee en ORM

IGNORED_INDEXES = {
    # presents en prod, absents du modele (crees hors ORM ou survivants
    # d'une ancienne version du modele jamais nettoyee - create_all() ne
    # supprime jamais un index existant) :
    "ix_workspace_users_user_workspace",
    "ix_wallet_transactions_user_created",
    "ix_payments_user_id",
    "ix_payments_link_id",
    "ix_withdrawals_user_id",
    "ix_webhooks_user_id",
    "ix_webhook_delivery_logs_user_created",
    "ix_api_logs_id",
    "ix_profiles_id",
    "ix_wallet_transactions_id",
    "ix_wallets_id",
    "ix_withdrawals_id",
    # declares dans le modele (index=True/unique=True) mais jamais crees en
    # prod, puisque create_all() ne cree que les tables manquantes, jamais
    # les index manquants sur une table deja existante :
    "ix_users_account_id",
    "ix_users_stripe_customer_id",
    "ix_users_stripe_subscription_id",
    # withdrawals.stripe_payout_id : le modele attend un index UNIQUE nomme
    # selon la convention SQLAlchemy ; la prod a un index NON unique sous un
    # nom different. Les deux noms sont ignores ici pour ne pas proposer un
    # drop+create - a traiter via une migration dediee (cf. revision
    # 78e72802e47e pour le detail de l'ecart constate).
    "idx_withdrawals_stripe_payout_id",
    "ix_withdrawals_stripe_payout_id",
}

# Colonnes ou le modele et la prod divergent reellement (type ou
# nullabilite), decouvertes par autogenerate lors de l'adoption initiale
# (cf. revision 78e72802e47e). Exclues ici de la comparaison pour ne pas
# generer de modification inattendue ; a traiter via une migration dediee.
IGNORED_COLUMNS = {
    ("api_logs", "id"),            # modele=String, prod=INTEGER (SERIAL)
    ("users", "account_id"),       # modele=NOT NULL, prod=NULLABLE
}

# FK ou le comportement reel (ON DELETE) differe de ce que le modele
# laisse supposer - meme principe, meme revision de reference. La
# constraint cote modele (ForeignKey() sans nom explicite) n'a pas de nom
# au moment de la comparaison : on filtre donc par table, pas par nom.
IGNORED_FK_TABLES = {"webhook_delivery_logs"}


def include_object(object, name, type_, reflected, compare_to):
    if type_ == "table" and name in IGNORED_TABLES:
        return False
    if type_ == "index" and name in IGNORED_INDEXES:
        return False
    if type_ == "column" and object is not None:
        table_name = getattr(object.table, "name", None)
        if (table_name, name) in IGNORED_COLUMNS:
            return False
    if type_ == "foreign_key_constraint":
        table_name = getattr(getattr(object, "table", None), "name", None)
        if table_name in IGNORED_FK_TABLES:
            return False
    return True

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
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            include_object=include_object,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
