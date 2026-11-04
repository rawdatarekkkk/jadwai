"""Stable fingerprints of saved JSON inputs; no credentials or environment capture."""
import hashlib
import json
from pydantic import Field
from app.schemas import Strict

class SolverSettings(Strict):
    profile: str = Field(default="cp-sat-baseline-v1", pattern="^cp-sat-baseline-v1$")
    time_limit_seconds: int = Field(default=10, ge=1, le=60, strict=True)
    random_seed: int = Field(default=42, ge=0, le=2147483647, strict=True)
    search_workers: int = Field(default=2, ge=1, le=4, strict=True)
    objective_profile: str = Field(default="preferences-first-v1", pattern="^(preferences-first-v1|weighted-v1)$")
    preference_weight: int = Field(default=10, ge=1, le=100, strict=True)
    idle_weight: int = Field(default=1, ge=1, le=100, strict=True)


CONFIG = {"profile": "cp-sat-baseline-v1", "time_limit_seconds": 10,
          "random_seed": 42, "search_workers": 2}
VALIDATOR_VERSION = "independent-checks-v5-day-off-overtime"


def fingerprint(value):
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def seal_snapshot(snapshot, config=None):
    payload = {k: v for k, v in snapshot.items() if k != 'provenance'}
    payload['snapshot_schema_version'] = 2
    config = SolverSettings.model_validate(config or CONFIG).model_dump()
    return {**payload, 'provenance': {'format_version': 1, 'snapshot_sha256': fingerprint(payload),
            'solver_config': config, 'config_sha256': fingerprint(config)}}


def verify_snapshot(snapshot):
    saved = snapshot.get('provenance')
    if saved is None:
        return True  # Legacy snapshots retain their original coverage.
    try:
        settings=SolverSettings.model_validate(saved.get('solver_config')).model_dump()
    except (ValueError, TypeError):
        return False
    return (saved.get('format_version') == 1
            and saved.get('snapshot_sha256') == fingerprint({k:v for k,v in snapshot.items() if k!='provenance'})
            and saved.get('config_sha256') == fingerprint(saved.get('solver_config'))
            and all(settings.get(k)==v for k,v in saved['solver_config'].items()))
