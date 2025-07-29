from pydantic import BaseModel
from typing import List, Optional


class ResourceResponse(BaseModel):
    resourceName: str


class ResourceListResponse(BaseModel):
    resources: List[ResourceResponse]


class DeleteResponse(BaseModel):
    message: str


class ResourceCreateResponse(BaseModel):
    message: str


class CourseDescriptionFileResponse(BaseModel):
    file_id: str
    vector_store_id: str
    batch_id: str
    pdf_path: str 