from fastapi import FastAPI, HTTPException
import redis
import os
import socket

app = FastAPI(
    title="Kubernetes FastAPI & Redis Microservice",
    description="Cloud-native microservice demo showcasing Kubernetes load balancing, probes, and persistence.",
    version="1.0.0"
)

# Configuration from Kubernetes ConfigMap & Secret
REDIS_HOST = os.getenv("REDIS_HOST", "redis-service")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
SECRET_TOKEN = os.getenv("SECRET_TOKEN", "default-insecure-key")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Initialize Redis client
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)

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
