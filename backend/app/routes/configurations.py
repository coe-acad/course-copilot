from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
from typing import List, Optional
from ..services.mongo import (
    get_configurations_by_type,
    get_setting_by_category,
    get_all_settings,
    get_merged_settings,
    create_configuration,
    update_configuration,
    delete_configuration
)
from ..utils.verify_token import get_user_org_context
import logging

logger = logging.getLogger(__name__)
router = APIRouter()

class ConfigurationResponse(BaseModel):
    _id: str
    type: str
    key: Optional[str] = None
    label: str
    desc: Optional[str] = None
    url: Optional[str] = None
    order: Optional[int] = None
    category: Optional[str] = None
    options: Optional[List[str]] = None

class ConfigurationCreateRequest(BaseModel):
    _id: str
    type: str
    key: Optional[str] = None
    label: str
    desc: Optional[str] = None
    url: Optional[str] = None
    order: Optional[int] = None
    category: Optional[str] = None
    options: Optional[List[str]] = None

@router.get("/configurations/curriculum", response_model=List[ConfigurationResponse])
async def get_curriculum_configurations():
    """Get all curriculum feature configurations"""
    try:
        logger.info("Fetching curriculum configurations")
        configs = get_configurations_by_type("curriculum")
        return configs
    except Exception as e:
        logger.error(f"Error fetching curriculum configurations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/configurations/assessment", response_model=List[ConfigurationResponse])
async def get_assessment_configurations():
    """Get all assessment feature configurations"""
    try:
        logger.info("Fetching assessment configurations")
        configs = get_configurations_by_type("assessment")
        return configs
    except Exception as e:
        logger.error(f"Error fetching assessment configurations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/configurations/settings")
async def get_all_setting_configurations(ctx: dict = Depends(get_user_org_context)):
    """Get all setting configurations (merged: global + org-specific) with flattened options"""
    org_db_name = ctx.get("org_db_name")
    try:
        logger.info(f"Fetching all setting configurations for org: {org_db_name}")
        # Get merged settings
        merged = get_merged_settings(org_db_name)
        
        # Flatten options for dropdown compatibility (just return label strings)
        for setting in merged:
            setting["options"] = [
                opt["label"] if isinstance(opt, dict) else opt
                for opt in setting.get("options", [])
            ]
        
        return merged
    except Exception as e:
        logger.error(f"Error fetching setting configurations: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/configurations/settings/{category}", response_model=ConfigurationResponse)
async def get_setting_configuration(category: str):
    """Get a specific setting configuration by category"""
    try:
        logger.info(f"Fetching setting configuration for category: {category}")
        config = get_setting_by_category(category)
        if not config:
            raise HTTPException(status_code=404, detail=f"Setting configuration for category '{category}' not found")
        return config
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching setting configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/configurations", response_model=dict)
async def create_new_configuration(config: ConfigurationCreateRequest):
    """Create a new system configuration (admin only - future enhancement)"""
    try:
        logger.info(f"Creating new configuration: {config._id}")
        config_data = config.model_dump()
        create_configuration(config_data)
        return {"message": "Configuration created successfully", "id": config._id}
    except Exception as e:
        logger.error(f"Error creating configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/configurations/{config_id}", response_model=dict)
async def update_existing_configuration(config_id: str, config: ConfigurationCreateRequest):
    """Update an existing system configuration (admin only - future enhancement)"""
    try:
        logger.info(f"Updating configuration: {config_id}")
        config_data = config.model_dump(exclude={"_id"})  # Exclude _id from update
        update_configuration(config_id, config_data)
        return {"message": "Configuration updated successfully", "id": config_id}
    except Exception as e:
        logger.error(f"Error updating configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/configurations/{config_id}", response_model=dict)
async def delete_existing_configuration(config_id: str):
    """Delete a system configuration (admin only - future enhancement)"""
    try:
        logger.info(f"Deleting configuration: {config_id}")
        delete_configuration(config_id)
        return {"message": "Configuration deleted successfully", "id": config_id}
    except Exception as e:
        logger.error(f"Error deleting configuration: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

