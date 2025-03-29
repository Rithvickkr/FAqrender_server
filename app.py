from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import redis
import json
import hashlib
import os
import uvicorn


app = FastAPI()
model = SentenceTransformer('all-MiniLM-L6-v2')

# Redis with error handling
try:
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, decode_responses=True)
except redis.ConnectionError as e:
    print(f"❌ Redis connection failed: {e}")
    redis_client = None  # Fallback to no cache

class EmbedRequest(BaseModel):
    text: str

def get_cache_key(text: str) -> str:
    return f"embed:{hashlib.md5(text.encode()).hexdigest()}"

@app.get("/")
async def root():
    return {"message": "Embedding API is running! Use /embed to generate embeddings."}
  
@app.post("/embed")
async def embed(request: EmbedRequest):
    text = request.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Text cannot be empty")
    
    cache_key = get_cache_key(text)
    if redis_client:
        try:
            cached_result = redis_client.get(cache_key)
            if cached_result:
                return json.loads(cached_result)
        except redis.RedisError as e:
            print(f"❌ Redis error: {e}")

    embedding = model.encode([text], convert_to_tensor=False).tolist()[0]  # ❌ GPU removed
    if redis_client:
        try:
            redis_client.setex(cache_key, 86400, json.dumps({"embedding": embedding}))
        except redis.RedisError as e:
            print(f"❌ Redis cache set failed: {e}")
    
    return {"embedding": embedding}

@app.get("/health")
async def health_check():
    redis_status = "ok" if redis_client and redis_client.ping() else "down"
    return {"status": "ok", "redis": redis_status}  # ✅ GPU check removed
