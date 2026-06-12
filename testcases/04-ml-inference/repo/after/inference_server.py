"""Fraud-score model inference service — ML platform team."""

import logging
import time

logger = logging.getLogger(__name__)

MODEL_VERSION = "fraud-v3.2.1"
RISK_THRESHOLD = 0.9

FEATURE_NAMES = (
    "amount_zscore", "merchant_risk", "geo_velocity", "device_age_days",
    "card_age_days", "txn_hour_sin", "txn_hour_cos", "is_cnp",
)

# Shadow registry until the model-mesh rollout (MLP-77) completes.
MODEL_REGISTRY = {
    "fraud-v3.2.1": {"stage": "production", "auc": 0.943},
    "fraud-v3.3.0rc1": {"stage": "shadow", "auc": 0.951},
}


def normalize_features(features):
    mx = max((abs(f) for f in features), default=0.0)
    if mx == 0:
        return list(features)
    return [f / mx for f in features]


def warmup():
    for _ in range(3):
        _run_model([0.1] * len(FEATURE_NAMES))
    logger.info("model warmed up: model=%s passes=%d", MODEL_VERSION, 3)


def score_request(request_id, features):
    # Feature vectors are large; only serialize them when DEBUG is live.
    if logger.isEnabledFor(logging.DEBUG):
        logger.debug(
            "scoring: request_id=%s model=%s n_features=%d features=%s",
            request_id, MODEL_VERSION, len(features), list(features),
        )

    start = time.time()
    prediction = _run_model(features)
    latency_ms = (time.time() - start) * 1000.0

    logger.info(
        "scored: request_id=%s model=%s score=%.4f latency_ms=%.1f",
        request_id, MODEL_VERSION, prediction, latency_ms,
    )

    if prediction > RISK_THRESHOLD:
        logger.warning(
            "high-risk score: request_id=%s model=%s score=%.4f",
            request_id, MODEL_VERSION, prediction,
        )

    return {"request_id": request_id, "score": prediction, "model": MODEL_VERSION}


def score_batch(batch):
    results = []
    failed = 0
    for req_id, features in batch:
        try:
            results.append(score_request(req_id, features))
        except Exception:
            failed += 1
            logger.exception("scoring failed: request_id=%s model=%s", req_id, MODEL_VERSION)
            results.append(None)

    logger.info(
        "batch scored: model=%s total=%d failed=%d", MODEL_VERSION, len(batch), failed
    )
    return results


def _run_model(features):
    if not features:
        raise ValueError("empty feature vector")
    return min(0.99, sum(abs(f) for f in features) / (10.0 * len(features)))
