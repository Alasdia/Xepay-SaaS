# Rotation sécurisée des refresh tokens (cookie HttpOnly côté client, hash
# en base côté serveur). Voir backend/models.RefreshToken et l'audit de
# migration cookies : chaque rotation révoque l'ancien jeton et en émet un
# nouveau dans la même "famille" (family_id). La réutilisation d'un jeton
# déjà révoqué est traitée comme :
#   - une course bénigne entre requêtes concurrentes (deux onglets, deux
#     appels /refresh presque simultanés) si elle survient dans les
#     REFRESH_TOKEN_REUSE_GRACE_SECONDS qui suivent sa révocation -> un
#     nouveau jeton enfant est quand même émis, dans la même famille ;
#   - une tentative de vol sinon -> toute la famille est révoquée et
#     l'appelant doit se reconnecter entièrement.
#
# Révision (revue finale) : la révocation de l'ancien jeton et la pose du
# pointeur replaced_by sont désormais faites dans LA MÊME instruction
# UPDATE (claim atomique ci-dessous), jamais en deux commits séparés.
# Avant ce correctif, une requête concurrente pouvait observer un état
# intermédiaire — revoked_at posé, replaced_by encore NULL — entre les deux
# anciens commits, échouer à tort la vérification within_grace (qui exige
# replaced_by non NULL) et révoquer toute la famille alors qu'il s'agissait
# d'une course bénigne. Voir test_refresh_token_concurrency_postgres.py
# pour une reproduction avec deux threads et deux connexions PostgreSQL
# réellement concurrentes.
#
# Limite de session ABSOLUE (30 jours, ABSOLUTE_SESSION_MAX_DAYS) :
# session_started_at est posé une seule fois à la connexion initiale
# (issue_refresh_token) puis propagé TEL QUEL à chaque jeton enfant créé
# par une rotation — jamais réinitialisé. La rotation vérifie cette limite
# dans la MÊME instruction UPDATE que le claim (comme expires_at) : passé
# ce délai, plus aucune rotation ne réussit, quel que soit l'état individuel
# du jeton présenté, et toute la famille est révoquée -> reconnexion
# complète obligatoire.
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.models import RefreshToken, UserDB
from backend.security import (
    generate_refresh_token,
    hash_refresh_token,
    REFRESH_TOKEN_EXPIRE_DAYS,
    REFRESH_TOKEN_REUSE_GRACE_SECONDS,
    ABSOLUTE_SESSION_MAX_DAYS,
)


def _insert_token_row(
    db: Session, user_id: str, family_id: str, token_hash: str,
    now: datetime, session_started_at: datetime,
) -> None:
    row = RefreshToken(
        user_id=user_id,
        family_id=family_id,
        token_hash=token_hash,
        created_at=now,
        expires_at=now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        session_started_at=session_started_at,
    )
    db.add(row)
    db.commit()


def issue_refresh_token(db: Session, user_id: str) -> str:
    """Premier jeton d'une nouvelle famille — appelé au login (classique,
    2FA, Google). session_started_at démarre ICI, une seule fois pour toute
    la durée de vie de cette famille (voir ABSOLUTE_SESSION_MAX_DAYS)."""
    raw_token = generate_refresh_token()
    now = datetime.now(timezone.utc)
    _insert_token_row(
        db, user_id, family_id=str(uuid4()),
        token_hash=hash_refresh_token(raw_token), now=now, session_started_at=now,
    )
    return raw_token


def rotate_refresh_token(db: Session, raw_token: str):
    """Valide puis fait tourner un refresh token. Retourne
    (nouveau_raw_token, UserDB) en cas de succès, None sinon (jeton inconnu,
    expiré, limite de session absolue atteinte, ou réutilisation hors
    fenêtre de grâce -> famille révoquée)."""
    token_hash = hash_refresh_token(raw_token)
    now = datetime.now(timezone.utc)
    session_floor = now - timedelta(days=ABSOLUTE_SESSION_MAX_DAYS)

    # Le jeton enfant est généré AVANT la tentative de claim, pour pouvoir
    # poser revoked_at ET replaced_by dans la MÊME instruction UPDATE.
    # expires_at >= now et session_started_at >= session_floor dans le
    # WHERE : un jeton expiré OU dont la session a dépassé la limite
    # absolue n'est jamais "claimé" (donc jamais marqué replaced_by) — il
    # retombe sur la branche "déjà révoqué / expiré" ci-dessous, qui tue la
    # famille sans jamais laisser de replaced_by orphelin.
    new_raw = generate_refresh_token()
    new_hash = hash_refresh_token(new_raw)

    claim_result = db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at >= now,
            RefreshToken.session_started_at >= session_floor,
        )
        .values(revoked_at=now, replaced_by=new_hash)
    )
    won_claim = claim_result.rowcount == 1
    db.commit()

    if won_claim:
        old_row = db.query(RefreshToken).filter(
            RefreshToken.token_hash == token_hash
        ).first()
        user = db.query(UserDB).filter(UserDB.id == old_row.user_id).first()
        if not user or user.is_deleted:
            # L'ancien jeton reste révoqué (comportement voulu pour un
            # compte désactivé) ; le jeton enfant pré-généré n'est jamais
            # inséré, replaced_by reste un pointeur inoffensif vers un hash
            # qui n'existera jamais (personne ne détient le raw_token
            # correspondant).
            return None
        # session_started_at propagé TEL QUEL (jamais now) : c'est ce qui
        # empêche la rotation de repousser la limite absolue.
        _insert_token_row(
            db, old_row.user_id, old_row.family_id, new_hash, now,
            session_started_at=old_row.session_started_at,
        )
        return new_raw, user

    # Claim perdu : jeton inconnu, déjà révoqué (course légitime ou
    # réutilisation malveillante), expiré, ou limite de session absolue
    # dépassée.
    existing = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()

    if existing is None:
        return None  # jeton jamais émis / garbage

    already_expired = existing.expires_at is not None and existing.expires_at < now
    session_expired = (
        existing.session_started_at is None
        or existing.session_started_at < session_floor
    )
    # replaced_by n'est posé QUE par une rotation réussie (jamais par un
    # logout, cf. revoke_refresh_token), et toujours ATOMIQUEMENT avec
    # revoked_at (cf. claim ci-dessus) : plus d'état intermédiaire possible
    # où l'un est posé sans l'autre.
    within_grace = (
        existing.revoked_at is not None
        and existing.replaced_by is not None
        and (now - existing.revoked_at).total_seconds() <= REFRESH_TOKEN_REUSE_GRACE_SECONDS
    )

    if already_expired or session_expired or not within_grace:
        # Réutilisation en dehors de la fenêtre de grâce, jeton expiré, ou
        # limite de session absolue dépassée : dans tous ces cas, on tue
        # toute la famille (y compris un jeton courant issu d'une rotation
        # gagnante concurrente) -> reconnexion complète obligatoire.
        db.execute(
            update(RefreshToken)
            .where(
                RefreshToken.family_id == existing.family_id,
                RefreshToken.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        db.commit()
        return None

    # Course bénigne (deux requêtes concurrentes avec le même cookie pas
    # encore mis à jour côté client) : on émet quand même un nouveau jeton
    # enfant dans la même famille, sans pénaliser l'utilisateur légitime.
    # session_started_at à nouveau propagé tel quel, jamais réinitialisé.
    user = db.query(UserDB).filter(UserDB.id == existing.user_id).first()
    if not user or user.is_deleted:
        return None
    child_raw = generate_refresh_token()
    _insert_token_row(
        db, existing.user_id, existing.family_id, hash_refresh_token(child_raw), now,
        session_started_at=existing.session_started_at,
    )
    return child_raw, user


def revoke_refresh_token(db: Session, raw_token: str) -> None:
    """Logout : révoque toute la FAMILLE du jeton présenté, pas seulement ce
    jeton — sinon la fenêtre de grâce de rotate_refresh_token (pensée pour
    des courses bénignes entre requêtes concurrentes) traiterait une
    réutilisation juste après un logout comme une course légitime et
    réémettrait un jeton valide pour une session que l'utilisateur vient
    explicitement de fermer."""
    token_hash = hash_refresh_token(raw_token)
    now = datetime.now(timezone.utc)
    existing = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash
    ).first()
    if existing is None:
        return
    db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.family_id == existing.family_id,
            RefreshToken.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.commit()
