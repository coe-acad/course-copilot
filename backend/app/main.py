from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="Creator Co-Pilot API",
    description="AI-powered course creation and management system",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5500",
        "http://127.0.0.1:5500"
    ],  # Add your frontend origins here
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"message": "Welcome to the Creator Co-Pilot API v2"}

@app.get("/health")
def health_check():
    return {"status": "healthy"}

# Routers will be included here as you build out the API modules
from app.api import auth
app.include_router(auth.router)
# app.include_router(courses.router)
# app.include_router(resources.router)
# app.include_router(ai_studio.router)
