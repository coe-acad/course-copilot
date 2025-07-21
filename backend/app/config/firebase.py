import os
import firebase_admin
from firebase_admin import credentials, firestore, storage
from dotenv import load_dotenv
import logging

logger = logging.getLogger(__name__)

load_dotenv()

firebase_config = {
    "apiKey": os.getenv("FIREBASE_API_KEY"),
    "authDomain": os.getenv("FIREBASE_AUTH_DOMAIN"),
    "projectId": os.getenv("FIREBASE_PROJECT_ID"),
    "storageBucket": os.getenv("FIREBASE_STORAGE_BUCKET"),
    "messagingSenderId": os.getenv("FIREBASE_MESSAGING_SENDER_ID"),
    "appId": os.getenv("FIREBASE_APP_ID"),
    "databaseURL": os.getenv("databaseURL")
}

# Check if all required Firebase environment variables are set
required_firebase_vars = [
    "FIREBASE_PROJECT_ID",
    "FIREBASE_PRIVATE_KEY",
    "FIREBASE_CLIENT_EMAIL"
]

if not all(os.getenv(var) for var in required_firebase_vars):
    missing = [var for var in required_firebase_vars if not os.getenv(var)]
    logger.error(f"Missing required Firebase environment variables: {', '.join(missing)}")
    raise ValueError(f"Missing required Firebase environment variables: {', '.join(missing)}")

# Use environment variables for credentials
logger.info("Using Firebase credentials from environment variables.")
private_key = os.getenv("FIREBASE_PRIVATE_KEY")
if private_key:
    private_key = private_key.replace("\\n", "\n")

cred = credentials.Certificate({
    "type": "service_account",
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": private_key,
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": os.getenv("FIREBASE_AUTH_URI", "https://accounts.google.com/o/oauth2/auth"),
    "token_uri": os.getenv("FIREBASE_TOKEN_URI", "https://oauth2.googleapis.com/token"),
    "auth_provider_x509_cert_url": os.getenv("FIREBASE_AUTH_PROVIDER_X509_CERT_URL", "https://www.googleapis.com/oauth2/v1/certs"),
    "client_x509_cert_url": os.getenv("FIREBASE_CLIENT_X509_CERT_URL")
})

if not firebase_admin._apps:
    try:
        firebase_admin.initialize_app(cred, {
            'storageBucket': os.getenv("FIREBASE_STORAGE_BUCKET", 'creator-co-pilot.appspot.com')
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