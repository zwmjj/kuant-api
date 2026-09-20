import hashlib, secrets, time, hmac, base64, json
from fastapi import APIRouter, HTTPException
from api.schemas.auth import LoginRequest, TokenResponse
from api.config import USERS, SECRET_KEY

router = APIRouter()


def _sign(payload: str) -> str:
    """Full HMAC-SHA256 hex digest.

    This used to be truncated with [:16], leaving a 64-bit signature. There is
    no reason to throw away 192 bits of a tag that costs nothing to carry.
    """
    return hmac.new(SECRET_KEY.encode(), payload.encode(), 'sha256').hexdigest()


def _make_token(username: str) -> str:
    payload = json.dumps({'user': username, 'exp': int(time.time()) + 86400})
    return base64.urlsafe_b64encode(f"{payload}|{_sign(payload)}".encode()).decode()


def verify_token(token: str) -> str | None:
    try:
        decoded = base64.urlsafe_b64decode(token).decode()
        payload_str, sig = decoded.rsplit('|', 1)
        # compare_digest, not ==, so the comparison does not short-circuit on
        # the first differing byte and leak the expected value through timing.
        if not hmac.compare_digest(sig, _sign(payload_str)):
            return None
        payload = json.loads(payload_str)
        if payload['exp'] < time.time():
            return None
        return payload['user']
    except Exception:
        return None


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    # NOTE: passwords are compared as bare unsalted SHA-256. That is weak for a
    # password store -- it is fast to brute-force and gives no protection
    # against rainbow tables or against two users sharing a password being
    # visibly identical. It is kept here because KUANT_API_USERS is documented
    # as carrying sha256 hashes and changing the format would silently
    # invalidate every configured account. A real deployment should move to
    # a memory-hard KDF (argon2id or bcrypt) with a per-user salt.
    h = hashlib.sha256(req.password.encode()).hexdigest()
    expected = USERS.get(req.username, "")
    # Run compare_digest even when the user does not exist, so a missing
    # username and a wrong password take the same path.
    ok = hmac.compare_digest(expected, h) if expected else False
    if not ok:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _make_token(req.username)
    return TokenResponse(token=token, username=req.username)
