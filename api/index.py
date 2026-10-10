# api/index.py
from typing import List

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, Response

app = FastAPI()

CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "POST, GET, OPTIONS",
    "Access-Control-Allow-Headers": "*",
}


# Add CORS headers to EVERY response (even when no Origin header is sent),
# and answer OPTIONS preflight requests directly.
@app.middleware("http")
async def add_cors_headers(request: Request, call_next):
    if request.method == "OPTIONS":
        response = Response(status_code=204)
    else:
        try:
            response = await call_next(request)
        except Exception:
            response = JSONResponse({"error": "Internal error"}, status_code=500)
    for k, v in CORS_HEADERS.items():
        response.headers[k] = v
    return response


# Telemetry from q-vercel-latency.json, embedded so no file I/O is needed.
# Each row: [region, latency_ms, uptime_pct]
TELEMETRY = [["apac", 227.03, 97.318], ["apac", 211.52, 98.767], ["apac", 166.65, 98.62], ["apac", 174.43, 98.225], ["apac", 193.01, 97.541], ["apac", 165.58, 97.897], ["apac", 210.49, 99.479], ["apac", 152.23, 99.361], ["apac", 141.18, 97.46], ["apac", 145.29, 99.165], ["apac", 204.09, 98.625], ["apac", 209.81, 97.423], ["emea", 133.75, 98.543], ["emea", 161.88, 99.012], ["emea", 139.06, 99.257], ["emea", 148.4, 99.099], ["emea", 219.13, 98.619], ["emea", 186.31, 99.204], ["emea", 196.79, 97.511], ["emea", 218.87, 99.093], ["emea", 129.83, 98.554], ["emea", 125.68, 97.688], ["emea", 209.76, 97.957], ["emea", 151.33, 97.347], ["amer", 176.34, 98.647], ["amer", 186.87, 97.968], ["amer", 177.42, 97.49], ["amer", 161.9, 97.917], ["amer", 190, 97.991], ["amer", 175.38, 97.822], ["amer", 145.84, 98.527], ["amer", 202.79, 98.461], ["amer", 125.36, 98.46], ["amer", 102.48, 98.792], ["amer", 150.99, 99.2], ["amer", 159.81, 98.014]]


def percentile(values: List[float], q: float) -> float:
    """Linear-interpolation percentile (same as numpy.percentile default)."""
    s = sorted(values)
    if not s:
        return 0.0
    k = (len(s) - 1) * q / 100
    lo = int(k)
    hi = min(lo + 1, len(s) - 1)
    return s[lo] + (s[hi] - s[lo]) * (k - lo)


def compute(regions: List[str], threshold: float) -> dict:
    out = {}
    for region in regions:
        rows = [r for r in TELEMETRY if r[0] == region]
        if not rows:
            continue
        lat = [r[1] for r in rows]
        up = [r[2] for r in rows]
        out[region] = {
            "avg_latency": sum(lat) / len(lat),
            "p95_latency": percentile(lat, 95),
            "avg_uptime": sum(up) / len(up),
            "breaches": sum(1 for x in lat if x > threshold),
        }
    return out


@app.post("/{full_path:path}")
async def analytics(request: Request, full_path: str = ""):
    try:
        body = await request.json()
        regions = body.get("regions", [])
        threshold = float(body.get("threshold_ms", 180))
    except Exception:
        return JSONResponse({"error": "Invalid JSON body"}, status_code=400)
    metrics = compute(regions, threshold)
    # per-region metrics under "regions", and also at the top level
    return {"regions": metrics, **metrics}


@app.get("/{full_path:path}")
def health(full_path: str = ""):
    return {"message": "POST {\"regions\": [...], \"threshold_ms\": 180} to this URL"}
