# LMS Environment Setup Guide

## Required Environment Variables

Add the following to your backend `.env` file:

```bash
# ============================================
# LMS Configuration (Required for LMS Export)
# ============================================

# Base URL of your LMS platform (without trailing slash)
# Example: https://lms.yourcompany.com
LMS_BASE_URL=https://your-lms-platform.com
```

## Complete Example Configuration

Here's a complete example of what your `.env` file should look like:

```bash
# ============================================
# LMS Configuration
# ============================================
LMS_BASE_URL=https://your-lms-platform.com

# ============================================
# OpenAI Configuration
# ============================================
OPENAI_API_KEY=sk-your-api-key-here
OPENAI_MODEL=gpt-4o

# ============================================
# Firebase Configuration
# ============================================
FIREBASE_PROJECT_ID=your-firebase-project-id
FIREBASE_PRIVATE_KEY_ID=your-private-key-id
FIREBASE_PRIVATE_KEY="-----BEGIN PRIVATE KEY-----\nYourPrivateKeyHere\n-----END PRIVATE KEY-----\n"
FIREBASE_CLIENT_EMAIL=firebase-adminsdk@your-project.iam.gserviceaccount.com
FIREBASE_CLIENT_ID=your-client-id
FIREBASE_CLIENT_X509_CERT_URL=https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk%40your-project.iam.gserviceaccount.com

# ============================================
# Google OAuth Configuration
# ============================================
GOOGLE_CLIENT_ID=your-google-client-id.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=your-google-client-secret
GOOGLE_REDIRECT_URI=http://localhost:8000/api/callback

# ============================================
# API Configuration
# ============================================
API_HOST=0.0.0.0
API_PORT=8000

# ============================================
# CORS Configuration
# ============================================
CORS_ORIGINS=http://localhost:3000,http://localhost:8000
CORS_ALLOW_CREDENTIALS=True

# ============================================
# Debug Configuration
# ============================================
DEBUG=True
LOG_LEVEL=INFO
```

## Frontend Environment Setup

Create `.env` file in the `frontend/` directory:

```bash
REACT_APP_API_BASE_URL=http://localhost:8000
```

## Important Notes

### LMS_BASE_URL Configuration

1. **Format:** 
   - ✅ Correct: `https://lms.example.com`
   - ❌ Wrong: `https://lms.example.com/`
   - ❌ Wrong: `https://lms.example.com/api`

2. **Protocol:**
   - Use `https://` in production
   - Use `http://` only for local development

3. **Endpoint Construction:**
   - Backend automatically appends `/api/v1/auth/signin`
   - Full URL becomes: `{LMS_BASE_URL}/api/v1/auth/signin`

## Verification Steps

### 1. Check Configuration Loading

Start your backend server and look for configuration messages:

```bash
cd backend
uvicorn app.main:app --reload
```

You should see in the logs:
```
INFO: Configuration loaded successfully
INFO: LMS_BASE_URL: https://your-lms-platform.com
```

### 2. Test Backend Health

```bash
curl http://localhost:8000/health
```

Response should include:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "lms_configured": true
}
```

### 3. Test LMS Login Endpoint

```bash
curl --location 'http://localhost:8000/api/login-lms' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer YOUR_USER_TOKEN' \
--data-raw '{
    "email": "test@example.com",
    "password": "testpassword"
}'
```

Expected responses:

**Success (200):**
```json
{
  "message": "Successfully logged into LMS",
  "data": {
    "token": "jwt_token_from_lms",
    "user": {
      "id": "user_id",
      "email": "test@example.com",
      "name": "Test User"
    }
  }
}
```

**Configuration Error (500):**
```json
{
  "detail": "LMS base URL is not configured in server settings"
}
```

**Connection Error (503):**
```json
{
  "detail": "Connection error - Could not connect to LMS server"
}
```

## Troubleshooting

### "LMS base URL is not configured"

**Problem:** Backend can't find `LMS_BASE_URL` in environment

**Solutions:**
1. Verify `.env` file exists in `backend/` directory
2. Check `LMS_BASE_URL` is spelled correctly (case-sensitive)
3. Restart backend server after adding variable
4. Check for extra spaces or quotes around the value

### "Connection error - Could not connect to LMS server"

**Problem:** Backend can't reach the LMS platform

**Solutions:**
1. Verify `LMS_BASE_URL` is correct
2. Check LMS platform is accessible from your server
3. Check firewall/network settings
4. Try accessing `{LMS_BASE_URL}/api/v1/auth/signin` in browser
5. Verify no VPN or proxy blocking the connection

### "Request timeout - LMS server took too long to respond"

**Problem:** LMS platform is slow or unresponsive

**Solutions:**
1. Check LMS platform status
2. Try again later
3. Contact LMS platform administrators
4. Check if request timeout (30s) needs to be increased

### Frontend can't connect to backend

**Problem:** API calls from frontend failing

**Solutions:**
1. Verify `REACT_APP_API_BASE_URL` in frontend `.env`
2. Check backend is running on correct port
3. Check CORS configuration in backend
4. Check browser console for specific errors

## Production Configuration

### Environment-Specific Variables

**Development:**
```bash
LMS_BASE_URL=https://lms-dev.yourcompany.com
DEBUG=True
LOG_LEVEL=DEBUG
CORS_ORIGINS=http://localhost:3000
```

**Staging:**
```bash
LMS_BASE_URL=https://lms-staging.yourcompany.com
DEBUG=False
LOG_LEVEL=INFO
CORS_ORIGINS=https://staging.yourcompany.com
```

**Production:**
```bash
LMS_BASE_URL=https://lms.yourcompany.com
DEBUG=False
LOG_LEVEL=WARNING
CORS_ORIGINS=https://yourcompany.com
```

### Security Checklist

- [ ] Use HTTPS for all URLs in production
- [ ] Never commit `.env` file to version control
- [ ] Use different credentials for each environment
- [ ] Rotate API keys and secrets regularly
- [ ] Enable SSL/TLS verification in production
- [ ] Use environment variables or secret management service
- [ ] Restrict CORS origins to specific domains
- [ ] Enable rate limiting on login endpoints
- [ ] Monitor and log authentication attempts
- [ ] Implement token expiration and refresh

## Testing the Complete Flow

### 1. Start Backend
```bash
cd backend
source venv/bin/activate  # or venv\Scripts\activate on Windows
uvicorn app.main:app --reload
```

### 2. Start Frontend
```bash
cd frontend
npm start
```

### 3. Test in Browser
1. Navigate to `http://localhost:3000`
2. Login to the application
3. Go to Dashboard
4. Click "Export to LMS" button
5. Enter LMS credentials
6. Verify login success
7. Check browser console for logs
8. Check localStorage for `lms_token`

### 4. Check Backend Logs
Look for:
```
INFO: Request: POST /api/login-lms
INFO: Attempting to login to LMS at https://your-lms.com/api/v1/auth/signin
INFO: LMS login response status: 200
INFO: Successfully logged into LMS
INFO: User user_id successfully logged into LMS
```

## Support

If you encounter issues:

1. **Check Documentation:**
   - `LMS_EXPORT_FLOW.md` - Complete flow documentation
   - `LMS_IMPLEMENTATION_SUMMARY.md` - Implementation summary
   - `LMS_LOGIN_API.md` - API documentation

2. **Debugging Steps:**
   - Enable DEBUG mode in backend
   - Check backend logs for detailed errors
   - Use browser DevTools to inspect network requests
   - Test backend endpoint directly with curl
   - Verify all environment variables are set

3. **Common Issues:**
   - Missing or incorrect environment variables
   - CORS errors (check CORS_ORIGINS)
   - Network connectivity issues
   - Invalid LMS credentials
   - LMS platform unavailable

## Additional Resources

- FastAPI documentation: https://fastapi.tiangolo.com/
- React environment variables: https://create-react-app.dev/docs/adding-custom-environment-variables/
- Python dotenv: https://pypi.org/project/python-dotenv/

