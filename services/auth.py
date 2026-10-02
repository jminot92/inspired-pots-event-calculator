import hashlib
import hmac
import secrets


def hash_password(password):
    if len(password) < 8:
        raise ValueError("Use a password of at least 8 characters.")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), 600_000).hex()
    return f"pbkdf2_sha256$600000${salt}${digest}"


def check_password(password, encoded):
    try:
        _, rounds, salt, expected = encoded.split("$")
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt.encode(), int(rounds)).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, AttributeError):
        return False


def require_admin(user):
    if not user or not user.active or user.role != "Admin":
        raise PermissionError("Administrator access is required.")


def can_edit(user, quote):
    return user.active and (user.role == "Admin" or quote.salesperson_id == user.id)
