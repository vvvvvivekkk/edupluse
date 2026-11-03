"""Loads the trained Random Forest and produces state estimates with explanations."""
import json
from functools import lru_cache

import pandas as pd

from ..config import MODEL_DIR
from .features import FEATURE_LABELS, FEATURE_NAMES, validate_features

STATE_LABELS = {
    "normal": "Normal",
    "attention_needed": "Attention Needed",
    "high_support_need": "High Support Need",
}


@lru_cache(maxsize=1)
def load_model():
    import joblib
    path = MODEL_DIR / "state_model.joblib"
    if not path.exists():
        from .train import train
        train(verbose=False)
    bundle = joblib.load(path)
    card = json.loads((MODEL_DIR / "model_card.json").read_text(encoding="utf-8"))
    return bundle, card


def predict_state(features: dict) -> dict:
    missing = validate_features(features)
    bundle, card = load_model()
    pipe = bundle["pipeline"]
    row = pd.DataFrame([{f: (features.get(f) if features.get(f) is not None else float("nan"))
                         for f in FEATURE_NAMES}])
    proba = pipe.predict_proba(row)[0]
    classes = list(pipe.classes_)
    state = classes[int(proba.argmax())]

    # Explanation: indicators that sit below the training median, ranked by global importance.
    medians, imp = card["training_medians"], card["feature_importance"]
    concerns = []
    for f in sorted(FEATURE_NAMES, key=lambda k: -imp.get(k, 0)):
        v = features.get(f)
        if v is not None and v < medians[f]:
            concerns.append(f"{FEATURE_LABELS[f]} {v:.0f}% is below the typical {medians[f]:.0f}%")
    return {
        "state": state,
        "state_label": STATE_LABELS[state],
        "probabilities": {c: round(float(p), 4) for c, p in zip(classes, proba)},
        "imputed_features": missing,
        "model_version": bundle["version"],
        "explanation": {
            "summary": (f"Estimated '{STATE_LABELS[state]}' with probability {proba.max():.0%}. "
                        "This is guidance for academic support, not a judgment of ability."),
            "concerns": concerns[:4],
            "imputed_note": (f"Not available, filled with training median: "
                             f"{', '.join(FEATURE_LABELS[m] for m in missing)}" if missing else None),
        },
    }
