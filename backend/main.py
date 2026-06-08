import os
import sys
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from routers.flows import router as flows_router
from ws.execute import websocket_endpoint

app = FastAPI(
    title="Flow Editor API",
    description="Visual Flow Editor and Execution Engine API",
    version="1.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(flows_router)
app.add_websocket_route("/ws/execute", websocket_endpoint)


@app.get("/api/health")
async def health_check():
    return {"status": "ok", "message": "Flow Engine API is running"}


frontend_dist = os.path.join(BASE_DIR, "..", "frontend", "dist")
if os.path.exists(frontend_dist):
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
