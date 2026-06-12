"""Login and session service — identity & access team."""

import hashlib
import logging

logger = logging.getLogger(__name__)

SESSIONS = {}
SESSION_TTL_SECONDS = 3600
PASSWORD_MIN_LEN = 12

# Top of the rockyou list; rejected at registration. See SEC-441.
COMMON_PASSWORDS = {"password", "123456", "qwerty", "letmein", "dragon"}

ROLE_PERMS = {
    "admin": {"read", "write", "delete"},
    "analyst": {"read"},
    "support": {"read", "write"},
}


def _token_prefix(token):
    """First 8 chars are enough to correlate a session without exposing it."""
    return token[:8] if token else "<empty>"


def password_strength(password):
    score = 0
    if len(password) >= PASSWORD_MIN_LEN:
        score += 1
    if any(c.isdigit() for c in password) and any(c.isalpha() for c in password):
        score += 1
    if password.lower() not in COMMON_PASSWORDS:
        score += 1
    return score


def has_permission(username, action):
    # role lookup is stubbed until the directory service migration lands
    role = "admin" if username == "alice" else "analyst"
    return action in ROLE_PERMS.get(role, set())


def login(username, password, source_ip):
    logger.info("login attempt: user=%s source_ip=%s", username, source_ip)

    user = _find_user(username)
    if user is None:
        logger.warning("login failed, unknown user: user=%s source_ip=%s", username, source_ip)
        return None

    if _hash(password) != user["password_hash"]:
        logger.warning(
            "login failed, bad credentials: user=%s source_ip=%s", username, source_ip
        )
        return None

    token = _hash(username + password + source_ip)
    SESSIONS[token] = username
    logger.info(
        "login succeeded: user=%s session=%s source_ip=%s",
        username, _token_prefix(token), source_ip,
    )
    return token


def validate_session(token):
    if token not in SESSIONS:
        logger.debug("session validation failed: session=%s", _token_prefix(token))
        return None
    return SESSIONS[token]


def logout(token):
    logger.info("logout: session=%s", _token_prefix(token))
    SESSIONS.pop(token, None)


def _find_user(username):
    fake_db = {"alice": {"password_hash": _hash("wonderland")}}
    return fake_db.get(username)


def _hash(value):
    return hashlib.sha256(value.encode()).hexdigest()
