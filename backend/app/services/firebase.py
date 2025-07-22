import os
import firebase_admin
from firebase_admin import credentials, firestore, storage
import logging
from ..config.settings import settings

logger = logging.getLogger(__name__)

firebase_config = {
    "apiKey": settings.FIREBASE_API_KEY,
    "authDomain": settings.FIREBASE_AUTH_DOMAIN,
    "projectId": settings.FIREBASE_PROJECT_ID,
    "storageBucket": settings.FIREBASE_STORAGE_BUCKET,
    "messagingSenderId": settings.FIREBASE_MESSAGING_SENDER_ID,
    "appId": settings.FIREBASE_APP_ID,
    "databaseURL": settings.DATABASE_URL
}

cred = credentials.Certificate({
    "type": "service_account",
    "project_id": settings.FIREBASE_PROJECT_ID,
    "private_key_id": settings.FIREBASE_PRIVATE_KEY_ID,
    "private_key": settings.FIREBASE_PRIVATE_KEY.replace("\\n", "\n") if settings.FIREBASE_PRIVATE_KEY else None,
    "client_email": settings.FIREBASE_CLIENT_EMAIL,
    "client_id": settings.FIREBASE_CLIENT_ID,
    "auth_uri": settings.FIREBASE_AUTH_URI,
    "token_uri": settings.FIREBASE_TOKEN_URI,
    "auth_provider_x509_cert_url": settings.FIREBASE_AUTH_PROVIDER_X509_CERT_URL,
    "client_x509_cert_url": settings.FIREBASE_CLIENT_X509_CERT_URL
})

if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app(cred, {
            'storageBucket': settings.FIREBASE_STORAGE_BUCKET
        })
    except Exception as e:
        logger.error(f"Failed to initialize Firebase Admin SDK: {str(e)}")
        raise ValueError(f"Failed to initialize Firebase Admin SDK: {str(e)}")

db = firestore.client()

# Initialize storage bucket with error handling
try:
    storage_bucket = storage.bucket('creator-co-pilot.appspot.com')
    # Test if bucket exists by trying to list files
    list(storage_bucket.list_blobs(max_results=1))
    logger.info("Firebase Storage bucket initialized successfully")
except Exception as e:
    logger.error(f"Failed to initialize storage bucket 'creator-co-pilot.appspot.com': {str(e)}")
    logger.warning("Firebase Storage is not available. File uploads will use placeholder URLs.")
    storage_bucket = None