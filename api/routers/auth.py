import hashlib, secrets, time, hmac, base64, json
from fastapi import APIRouter, HTTPException
from api.schemas.auth import LoginRequest, TokenResponse
from api.config import USERS, SECRET_KEY

router = APIRouter()


def _make_token(username: str) -> str:
    payload = json.dumps({'user': username, 'exp': int(time.time()) + 86400})
    sig = hmac.new(SECRET_KEY.encode(), payload.encode(), 'sha256').hexdigest()[:16]
    return base64.urlsafe_b64encode(f"{payload}|{sig}".encode()).decode()


def verify_token(token: str) -> str | None:
    try:
        decoded = base64.urlsafe_b64decode(token).decode()
        payload_str, sig = decoded.rsplit('|', 1)
        expected = hmac.new(SECRET_KEY.encode(), payload_str.encode(), 'sha256').hexdigest()[:16]
        if sig != expected:
            return None
        payload = json.loads(payload_str)
        if payload['exp'] < time.time():
            return None
        return payload['user']
    except Exception:
        return None


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    h = hashlib.sha256(req.password.encode()).hexdigest()
    if req.username not in USERS or USERS[req.username] != h:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = _make_token(req.username)
    return TokenResponse(token=token, username=req.username)
