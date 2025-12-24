import os
from openai import OpenAI
from ..config.settings import settings
import logging

logger = logging.getLogger(__name__)

# Initialize client with v2 API header using settings
client = OpenAI(
    api_key=settings.OPENAI_API_KEY,
)

logger.info("OpenAI client initialized with v2 API configuration")

