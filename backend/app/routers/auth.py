from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .. import models, serializers
from ..database import get_db
from ..security import create_access_token, get_current_user, verify_password
from ..services_common import audit

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginIn(BaseModel):
    email: str
    password: str


def _authenticate(db: Session, email: str, password: str) -> models.User:
    u = db.query(models.User).filter(models.User.email == email.strip().lower()).first()
    if not u or not verify_password(password, u.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if not u.is_active:
        raise HTTPException(status_code=403, detail="This account is deactivated")
    return u


@router.post("/login")
def login(body: LoginIn, db: Session = Depends(get_db)):
    """Authenticate with email + password; returns a bearer token and the user (with role for redirect)."""
    u = _authenticate(db, body.email, body.password)
    audit(db, u.id, "login", "users", u.id)
    db.commit()
    return {"access_token": create_access_token(u), "token_type": "bearer", "user": serializers.user(u)}


@router.post("/token", include_in_schema=True)
def token(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    """OAuth2 form login (used by the Swagger 'Authorize' button)."""
    u = _authenticate(db, form.username, form.password)
    return {"access_token": create_access_token(u), "token_type": "bearer"}


@router.get("/me")
def me(user: models.User = Depends(get_current_user)):
    return serializers.user(user)
