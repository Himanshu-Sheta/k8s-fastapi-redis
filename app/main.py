from fastapi import FastAPI, HTTPException, Request
from starlette.responses import Response
import redis
import os
import socket
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import time

app = FastAPI(
    title="Kubernetes FastAPI & Redis Microservice",
    description="Cloud-native microservice demo showcasing Kubernetes load balancing, probes, persistence, and Prometheus observability.",
    version="1.1.0"
)

# Configuration from Kubernetes ConfigMap & Secret
REDIS_HOST = os.getenv("REDIS_HOST", "redis-service")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
SECRET_TOKEN = os.getenv("SECRET_TOKEN", "default-insecure-key")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Initialize Redis client
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

# Prometheus Metrics Definitions
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests processed",
    ["method", "endpoint", "status_code"]
)
HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "Duration of HTTP requests in seconds",
    ["method", "endpoint"]
)

@app.middleware("http")
async def prometheus_metrics_middleware(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    
    endpoint = request.url.path
    # Group item paths together to prevent high metric cardinality
    if endpoint.startswith("/items/"):
        endpoint = "/items/{key}"

    HTTP_REQUESTS_TOTAL.labels(
        method=request.method,
        endpoint=endpoint,
        status_code=response.status_code
    ).inc()
    
    HTTP_REQUEST_DURATION_SECONDS.labels(
        method=request.method,
        endpoint=endpoint
    ).observe(duration)
    
    return response

@app.get("/")
def read_root():
    """Demonstrates Kubernetes load balancing across pods and cache increment."""
    pod_name = socket.gethostname()
    try:
        r.incr("hit_counter")
        hits = r.get("hit_counter")
    except Exception as e:
        hits = f"Redis error: {str(e)}"

    return {
        "status": "online",
        "environment": ENVIRONMENT,
        "served_by_pod": pod_name,
        "total_hits": hits,
        "message": "Hello from Kubernetes! Refresh to see requests handled across different pods."
    }

@app.get("/health")
def health_check():
    """Health endpoint for Kubernetes Liveness and Readiness probes."""
    try:
        r.ping()
        return {"status": "healthy", "redis": "connected"}
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Redis unavailable: {str(e)}")

@app.get("/metrics")
def metrics():
    """Prometheus metrics scraping endpoint."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/items/{key}")
def set_item(key: str, value: str):
    """Store an item in Redis to demonstrate persistent volume storage."""
    try:
        r.set(key, value)
        return {"status": "success", "key": key, "value": value}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/items/{key}")
def get_item(key: str):
    """Retrieve an item from Redis."""
    try:
        val = r.get(key)
        if val is None:
            raise HTTPException(status_code=404, detail="Key not found")
        return {"key": key, "value": val}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
