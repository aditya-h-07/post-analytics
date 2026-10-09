import json
import math
from pathlib import Path
from fastapi.responses import Response

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

@app.options("/")
@app.options("/analytics")
def cors_preflight():
    return Response(
        status_code=204,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        },
    )

@app.middleware("http")
async def ensure_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "*"
    return response

DATA_FILE = Path(__file__).resolve().parent.parent / "telemetry.json"


class AnalyticsRequest(BaseModel):
    regions: list[str]
    threshold_ms: float = 180


def percentile95(values):
    values = sorted(values)
    if not values:
        return 0.0

    position = 0.95 * (len(values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)

    return values[lower] + (
        values[upper] - values[lower]
    ) * (position - lower)


@app.post("/")
@app.post("/analytics")
def analytics(request: AnalyticsRequest):
    try:
        with open(DATA_FILE, encoding="utf-8") as f:
            records = json.load(f)
    except (OSError, json.JSONDecodeError):
        raise HTTPException(
            status_code=500,
            detail="Unable to load telemetry data",
        )

    result = {}

    for region in request.regions:
        selected = [
            r for r in records
            if r.get("region", "").lower() == region.lower()
        ]

        latencies = [float(r["latency_ms"]) for r in selected]
        uptimes = [float(r["uptime_pct"]) for r in selected]

        result[region] = {
            "avg_latency": (
                sum(latencies) / len(latencies) if latencies else 0
            ),
            "p95_latency": percentile95(latencies),
            "avg_uptime": (
                sum(uptimes) / len(uptimes) if uptimes else 0
            ),
            "breaches": sum(
                x > request.threshold_ms for x in latencies
            ),
        }

    return result
