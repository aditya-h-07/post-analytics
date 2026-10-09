
import json
import math
from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()

# Standard CORS support for browser preflight requests
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# Always attach CORS headers, even when Origin is absent
@app.middleware("http")
async def add_cors_headers(request, call_next):
    response = await call_next(request)
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
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
@app.post("/api/latency")
def analytics(request: AnalyticsRequest):
    try:
        with open(DATA_FILE, encoding="utf-8") as file:
            records = json.load(file)
    except (OSError, json.JSONDecodeError):
        raise HTTPException(
            status_code=500,
            detail="Unable to load telemetry data",
        )

    result = {}

    for region in request.regions:
        selected = [
            record
            for record in records
            if record.get("region", "").lower() == region.lower()
        ]

        latencies = [
            float(record["latency_ms"]) for record in selected
        ]
        uptimes = [
            float(record["uptime_pct"]) for record in selected
        ]

        result[region] = {
            "avg_latency": (
                sum(latencies) / len(latencies) if latencies else 0
            ),
            "p95_latency": percentile95(latencies),
            "avg_uptime": (
                sum(uptimes) / len(uptimes) if uptimes else 0
            ),
            "breaches": sum(
                latency > request.threshold_ms
                for latency in latencies
            ),
        }

    return result