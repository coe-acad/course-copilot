from fastapi import APIRouter, Depends, HTTPException, status
from app.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["auth"])

@router.get("/me")
def get_me(user=Depends(get_current_user)):
    return {"user": user} 