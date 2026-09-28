import os
import time
import uuid

import redis
from dotenv import load_dotenv

load_dotenv()

WINDOW_SECONDS = 15 * 60
MAX_ATTEMPTS = 5

REDIS_URL = os.getenv("REDIS_URL")

_redis_client = (
    redis.Redis.from_url(
        REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=1,
        socket_timeout=1,
    )
    if REDIS_URL
    else None
)

# Purge les entrées hors fenêtre, puis n'ajoute la tentative que si la limite
# n'est pas déjà atteinte. Exécuté atomiquement par Redis (mono-thread) : sous
# forte concurrence multi-replicas, la Nième+1 tentative simultanée est
# rejetée par ce script avant tout appel à totp.verify() côté applicatif.
_ALLOW_ATTEMPT_SCRIPT = """
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1] - ARGV[2])
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[3]) then
    return 0
end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
redis.call('EXPIRE', KEYS[1], ARGV[2])
return 1
"""


def allow_attempt(key: str) -> bool:
    """Consomme atomiquement un slot pour `key` s'il en reste sous la fenêtre
    glissante WINDOW_SECONDS / MAX_ATTEMPTS. Fail-closed : si Redis est
    injoignable ou mal configuré (REDIS_URL absente), renvoie False plutôt que
    de lever une exception ou de laisser passer la tentative sans limite."""
    if _redis_client is None:
        return False
    try:
        now = time.time()
        member = f"{now}:{uuid.uuid4()}"
        result = _redis_client.eval(
            _ALLOW_ATTEMPT_SCRIPT,
            1,
            key,
            now,
            WINDOW_SECONDS,
            MAX_ATTEMPTS,
            member,
        )
        return bool(result)
    except redis.RedisError:
        return False


def reset(key: str) -> None:
    """Supprime le compteur de `key` (à appeler après un succès réel)."""
    if _redis_client is None:
        return
    try:
        _redis_client.delete(key)
    except redis.RedisError:
        pass
