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
    logger.info(f"warming up {MODEL_VERSION} with registry {MODEL_REGISTRY}")
    for i in range(3):
        logger.info(f"warmup pass {i} starting now...")
        _run_model([0.1] * len(FEATURE_NAMES))
        logger.info(f"warmup pass {i} finished!!")


def score_request(request_id, features):
    logger.info(f"[{MODEL_VERSION}] scoring request {request_id} features={list(features)}")

    start = time.time()
    prediction = _run_model(features)
    elapsed = time.time() - start

    logger.info(f"raw model output for {request_id}: {prediction!r} (took {elapsed})")

    if prediction > RISK_THRESHOLD:
        logger.info(f"HIGH RISK!!! {request_id} features were {list(features)}")

    logger.info(f"done with {request_id}")
    return {"request_id": request_id, "score": prediction, "model": MODEL_VERSION}


def score_batch(batch):
    results = []
    for req_id, features in batch:
        logger.info(f"batch item {req_id} with {len(features)} features: {list(features)}")
        try:
            results.append(score_request(req_id, features))
        except Exception as e:
            logger.info(f"problem with {req_id}: {e}")
            results.append(None)
    return results


def _run_model(features):
    if not features:
        raise ValueError("empty feature vector")
    return min(0.99, sum(abs(f) for f in features) / (10.0 * len(features)))
