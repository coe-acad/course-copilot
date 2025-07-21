from fastapi import HTTPException
import logging

logger = logging.getLogger(__name__)

class CourseError(Exception):
    """Base exception for course-related errors"""
    pass

class CourseNotFoundError(CourseError):
    """Raised when a course is not found"""
    pass

class UnauthorizedError(CourseError):
    """Raised when user is not authorized for a resource"""
    pass

class ResourceError(CourseError):
    """Base exception for resource-related errors"""
    pass

class ResourceNotFoundError(ResourceError):
    """Raised when a resource is not found"""
    pass

class ResourceAlreadyCheckedOutError(ResourceError):
    """Raised when trying to check out an already checked out resource"""
    pass

class ResourceAlreadyCheckedInError(ResourceError):
    """Raised when trying to check in an already checked in resource"""
    pass

class OpenAIError(CourseError):
    """Raised when there's an error with OpenAI API"""
    pass

def handle_course_error(error: Exception) -> HTTPException:
    """Convert course errors to HTTP exceptions"""
    if isinstance(error, CourseNotFoundError):
        logger.error(f"Course not found: {str(error)}")
        return HTTPException(status_code=404, detail="Course not found")
    elif isinstance(error, UnauthorizedError):
        logger.error(f"Unauthorized access: {str(error)}")
        return HTTPException(status_code=403, detail="Unauthorized access")
    elif isinstance(error, ResourceNotFoundError):
        logger.error(f"Resource not found: {str(error)}")
        return HTTPException(status_code=404, detail="Resource not found")
    elif isinstance(error, ResourceAlreadyCheckedOutError):
        logger.error(f"Resource already checked out: {str(error)}")
        return HTTPException(status_code=400, detail="Resource is already checked out")
    elif isinstance(error, ResourceAlreadyCheckedInError):
        logger.error(f"Resource already checked in: {str(error)}")
        return HTTPException(status_code=400, detail="Resource is already checked in")
    elif isinstance(error, OpenAIError):
        logger.error(f"OpenAI API error: {str(error)}")
        return HTTPException(status_code=500, detail=f"OpenAI API error: {str(error)}")
    else:
        logger.error(f"Unexpected course error: {str(error)}")
        return HTTPException(status_code=500, detail=f"Internal server error: {str(error)}") 