"""Password hashing (bcrypt), JWT tokens and role-based access helpers."""
from datetime import datetime, timedelta, timezone

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from . import models
from .config import ACCESS_TOKEN_MINUTES, JWT_ALGORITHM, SECRET_KEY
from .database import get_db

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return pwd_context.verify(password, hashed)


def create_access_token(user: models.User) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_MINUTES)
    payload = {"sub": str(user.id), "role": user.role, "exp": expire}
    return jwt.encode(payload, SECRET_KEY, algorithm=JWT_ALGORITHM)


def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    cred_exc = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                             detail="Invalid or expired token",
                             headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
        user_id = int(payload.get("sub"))
    except (JWTError, TypeError, ValueError):
        raise cred_exc
    user = db.get(models.User, user_id)
    if not user or not user.is_active:
        raise cred_exc
    return user


def require_roles(*roles: str):
    def checker(user: models.User = Depends(get_current_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Not permitted for your role")
        return user
    return checker


def authorized_student_ids(db: Session, user: models.User) -> list[int] | None:
    """Student profile ids the user may see. None means 'all' (admin)."""
    if user.role == "admin":
        return None
    if user.role == "student":
        return [user.student_profile.id] if user.student_profile else []
    if user.role == "faculty":
        if not user.faculty_profile:
            return []
        rows = db.query(models.FacultyStudentAssignment.student_id).filter(
            models.FacultyStudentAssignment.faculty_id == user.faculty_profile.id).all()
        return [r[0] for r in rows]
    return []


def ensure_student_access(db: Session, user: models.User, student_id: int) -> models.StudentProfile:
    student = db.get(models.StudentProfile, student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    allowed = authorized_student_ids(db, user)
    if allowed is not None and student_id not in allowed:
        # 403 rather than 404 is deliberate for clarity in the demo; it does not leak record content.
        raise HTTPException(status_code=403, detail="You are not authorised to view this student")
    return student
