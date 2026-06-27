import os
import sys
import logging
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv, find_dotenv


CURPATH = os.path.abspath(os.path.dirname(__file__))
sys.path.append(CURPATH)
sys.path.append(os.path.join(CURPATH, "agent"))

# Load environment variables. override=True so values in .env are authoritative
# over any stale OPENAI_API_KEY/etc. exported in the shell or conda environment.
load_dotenv(find_dotenv(), override=True)

# -------------------------------
# Logging Configuration
# -------------------------------
logging.basicConfig(
    level=logging.INFO,  # Change to DEBUG for more detail
    format="[%(levelname)s] %(name)s: %(message)s",
)

# Reduce noise from some libraries
logging.getLogger("uvicorn.error").setLevel(logging.INFO)
logging.getLogger("uvicorn.access").setLevel(logging.INFO)
logging.getLogger("azure").setLevel(logging.WARNING)

# Create a logger for this module
logger = logging.getLogger(__name__)
logger.info("Logging is configured and ready.")

root_path = os.getenv('ROOT_PATH', '')
api_server = os.getenv('API_SERVER', 'http://localhost:8000')

# Ensure URL scheme is correct
if not api_server.startswith(('http://', 'https://')):
    raise ValueError("API_SERVER URL scheme must be 'http' or 'https'")

# Initialize FastAPI
app = FastAPI(
    root_path=root_path, 
    servers=[
        { "url": api_server, "description": "UAT Environment" }
    ],
    openapi_url="/openapi.json",
    docs_url="/docs",
    redoc_url="/redoc"
)

@app.get("/")
async def healthcheck():
    return "Service is RUNNING"

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


from fastapi.staticfiles import StaticFiles

from agent import market_agent_api

# Serve generated charts (and any static assets) at /static
_STATIC_DIR = os.path.join(CURPATH, "static")
os.makedirs(os.path.join(_STATIC_DIR, "charts"), exist_ok=True)
app.mount("/static", StaticFiles(directory=_STATIC_DIR), name="static")

# Include the Sentinel market agent router
app.include_router(market_agent_api.market_agent_router, prefix="/market_agent")


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
