from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from .routes import auth, course, resources, chat, course_outcomes
from .config.settings import settings
import logging

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.LOG_LEVEL),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Creator Copilot API",
    description="AI-powered course creation and management system",
    version="1.0.0",
    debug=settings.DEBUG
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:8501", "*"],  # Configure properly for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth")
app.include_router(course.router, prefix="/api")
app.include_router(resources.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(course_outcomes.router, prefix="/api")

# Add callback route at root level to match Google OAuth redirect
from .routes.auth import google_callback
app.add_api_route("/callback", google_callback, methods=["GET"])

@app.get("/")
async def root():
    return {"message": "Welcome to the Creator Copilot API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "openai_configured": bool(settings.OPENAI_API_KEY),
        "firebase_configured": bool(settings.FIREBASE_PROJECT_ID)
    }

if __name__ == "__main__":
    import uvicorn
    logger.info(f"Starting Creator Copilot API on {settings.API_HOST}:{settings.API_PORT}")
    uvicorn.run(
        "main:app",
        host=settings.API_HOST,
        port=settings.API_PORT,
        reload=settings.DEBUG
    )