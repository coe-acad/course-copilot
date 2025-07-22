from ..services.firebase import db, firebase_config
from firebase_admin import auth as admin_auth
import pyrebase
import uuid

# Initialize pyrebase for client-side auth
firebase = pyrebase.initialize_app(firebase_config)
client_auth = firebase.auth()

def signup_user(email, password, name):
    try:
        user = client_auth.create_user_with_email_and_password(email, password)
        user_id = user['localId']  # Use Firebase UID
        # Save user details to Firestore
        db.collection("users").document(user_id).set({
            "email": email,
            "name": name,
            "firebase_uid": user_id
        })
        return {"message": "Signup successful", "user_id": user_id}, 200
    except Exception as e:
        return {"message": f"Signup failed: {str(e)}"}, 400

def login_user(email, password):
    try:
        user = client_auth.sign_in_with_email_and_password(email, password)
        return {"message": "Login successful", "token": user['idToken']}, 200
    except Exception as e:
        return {"message": "Invalid credentials"}, 401

def google_login(id_token):
    try:
        decoded_token = admin_auth.verify_id_token(id_token)
        uid = decoded_token['uid']
        user_record = admin_auth.get_user(uid)
        # Save user to Firestore if new
        user_doc = db.collection("users").document(uid).get()
        if not user_doc.exists:
            db.collection("users").document(uid).set({
                "email": user_record.email,
                "name": user_record.display_name or "Unknown",
                "firebase_uid": uid
            })
        return {
            "message": "Google login successful",
            "email": user_record.email,
            "token": id_token,
            "user_id": uid
        }, 200
    except Exception as e:
        return {"message": f"Google login failed: {str(e)}"}, 401