"""Application settings, read from environment variables (see .env.example)."""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql+psycopg2://edupulse:edupulse@localhost:5432/edupulse"
)
SECRET_KEY = os.getenv("SECRET_KEY", "change-me-in-production-please-32-chars-min")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_MINUTES = int(os.getenv("ACCESS_TOKEN_MINUTES", "480"))
MODEL_DIR = Path(os.getenv("MODEL_DIR", BASE_DIR / "models"))
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").split(",")

# Default values for the configurable policy. Admins can change these at runtime
# (stored in the system_config table); these are only the initial values.
DEFAULT_CONFIG = {
    # Combined reward r = alpha * g + (1 - alpha) * e
    "reward_alpha": 0.7,
    # Response classification thresholds on the bounded reward r in [-1, 1]
    "positive_threshold": 0.30,
    "partial_threshold": 0.05,
    # Linear Thompson sampling: prior precision (ridge regularisation) and posterior scale
    "lints_lambda": 1.0,
    "lints_v": 0.5,
    # Eligibility thresholds (percent scale 0-100 unless stated)
    "low_score_threshold": 60.0,
    "weak_mastery_threshold": 55.0,
    "low_attendance_threshold": 75.0,
    "low_completion_threshold": 70.0,
    "no_improvement_streak": 2,
    # Observation window for engagement measurement (days)
    "engagement_window_days": 14,
}
