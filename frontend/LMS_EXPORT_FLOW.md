# LMS Export Flow Documentation

## Overview
This document explains the complete flow for exporting content to the LMS (Learning Management System) platform, including both frontend and backend components.

## User Flow

1. **User clicks "Export to LMS"** in the Dashboard header
2. **LMS Login Modal appears** (`LMSLoginModal.js`)
   - User enters their LMS email and password
   - Form validates inputs (email format, required fields)
   - On submit, calls the backend login endpoint
3. **After successful login:**
   - LMS token is stored in localStorage
   - Export Assets Modal opens automatically
4. **Export Assets Modal** (`ExportAssetsModal.js`)
   - User selects assets to export
   - On export, assets are formatted and sent to LMS

## Frontend Components

### 1. LMSLoginModal.js
**Location:** `/frontend/src/components/LMSLoginModal.js`

**Features:**
- Email and password input fields
- Password visibility toggle
- Form validation (email format, required fields)
- Loading state during authentication
- Error handling with user-friendly messages
- Responsive, modern UI design

**Props:**
- `open` (boolean): Controls modal visibility
- `onClose` (function): Called when modal should close
- `onLoginSuccess` (function): Called after successful login with response data

**API Call:**
```javascript
POST /api/login-lms
Headers: 
  - Authorization: Bearer <user_token>
  - Content-Type: application/json
Body: {
  "email": "user@example.com",
  "password": "password123"
}
```

**Success Response:**
```json
{
  "message": "Successfully logged into LMS",
  "data": {
    "token": "lms_jwt_token",
    "user": {
      "id": "user_id",
      "email": "user@example.com",
      "name": "User Name"
    }
  }
}
```

**Storage:**
After successful login, the following are stored in localStorage:
- `lms_token`: JWT token from LMS for authenticated requests
- `lms_user`: JSON string of user information from LMS

### 2. DashboardLayout.js Updates
**Location:** `/frontend/src/layouts/DashboardLayout.js`

**Changes:**
- Added `LMSLoginModal` import
- Added state for `showLMSLoginModal`
- Changed "Export to LMS" button to open login modal first
- After successful login, automatically opens export modal
- Sequential flow: Login → Export

### 3. ExportAssetsModal.js (Existing)
**Location:** `/frontend/src/components/ExportAssetsModal.js`

**Current Functionality:**
- Displays all assets for the current course
- Allows filtering and searching assets
- Multi-select functionality with "Select All" option
- Exports selected assets to LMS format

**Future Enhancement Needed:**
The export functionality should use the stored `lms_token` when sending data to the LMS platform.

```javascript
// BACKEND: When implementing actual LMS export, use the stored token
const lmsToken = localStorage.getItem("lms_token");
// Include this token in requests to LMS platform
```

## Backend Components

### 1. Login Endpoint
**File:** `/backend/app/routes/exportlms.py`
**Route:** `POST /api/login-lms`

**Already Implemented:** ✅

**Request Model:**
```python
class LoginLMSRequest(BaseModel):
    email: str
    password: str
```

**Functionality:**
- Validates email and password are provided
- Calls `login_to_lms()` utility function
- Returns LMS authentication response
- Handles errors appropriately (400, 401, 500, 503, 408)

### 2. LMS Utility Function
**File:** `/backend/app/utils/lms_curl.py`
**Function:** `login_to_lms(email: str, password: str)`

**Already Implemented:** ✅

**Functionality:**
- Constructs URL: `{LMS_BASE_URL}/api/v1/auth/signin`
- Makes POST request with email and password
- Handles timeout (30 seconds)
- Handles connection errors
- Handles HTTP errors
- Returns structured response with success status and data

### 3. Export Endpoint
**File:** `/backend/app/routes/exportlms.py`
**Route:** `POST /api/courses/{course_id}/export-lms`

**Already Implemented:** ✅

**Functionality:**
- Exports selected assets from a course
- Currently supports quiz assets
- Formats content for LMS consumption
- Returns formatted data including course information

**Future Enhancement:**
```python
# BACKEND: To actually push content to LMS platform:
# 1. Receive LMS token from frontend (via header or request body)
# 2. Use the token to authenticate with LMS platform
# 3. Call LMS platform's API to create/update content
# 4. Handle LMS-specific formatting and requirements
# 5. Return success/failure status from LMS platform
```

## Environment Configuration

### Backend (.env)
The following environment variable must be set:

```bash
# LMS Platform Configuration
LMS_BASE_URL=https://your-lms-platform.com
```

**Note:** Do NOT include trailing slash in the URL.

### Frontend (.env)
```bash
REACT_APP_API_BASE_URL=http://localhost:8000
```

## Error Handling

### Frontend Error Messages
- **Empty Fields:** "Please enter both email and password"
- **Invalid Email:** "Please enter a valid email address"
- **Network Error:** "Failed to login to LMS. Please try again."
- **Backend Error:** Displays the error detail from backend response

### Backend Error Codes
- **400:** Missing email or password
- **401:** Invalid credentials
- **408:** Request timeout
- **500:** LMS base URL not configured or internal server error
- **503:** Connection error (LMS server unreachable)

## Security Considerations

1. **HTTPS Only:** Always use HTTPS in production
2. **Token Storage:** LMS token stored in localStorage (consider httpOnly cookies for production)
3. **Password Handling:** Passwords never stored, only transmitted over secure connection
4. **Token Expiration:** Frontend should handle token expiration and re-authentication
5. **CORS:** Ensure proper CORS configuration for LMS domain

## Testing

### Frontend Testing
```bash
cd frontend
npm start
```
1. Click "Export to LMS" in dashboard
2. Enter LMS credentials
3. Verify successful login and modal transition
4. Check browser console for stored token
5. Check localStorage for `lms_token` and `lms_user`

### Backend Testing
```bash
# Using curl
curl --location 'http://localhost:8000/api/login-lms' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer YOUR_AUTH_TOKEN' \
--data-raw '{
    "email": "user@example.com",
    "password": "password123"
}'
```

## Future Enhancements

### Backend
```python
# BACKEND: Implement actual content push to LMS
# File: backend/app/routes/exportlms.py or backend/app/utils/lms_export.py

def push_to_lms(lms_token: str, course_data: dict, assets: list) -> dict:
    """
    Push formatted content to LMS platform
    
    Args:
        lms_token: JWT token from LMS login
        course_data: Course information (name, description, etc.)
        assets: Formatted assets to export
    
    Returns:
        dict: Response from LMS platform with success status
        
    Implementation needed:
        1. Construct LMS API endpoint URL
        2. Set Authorization header with lms_token
        3. Format data according to LMS API requirements
        4. Make POST request to create/update content
        5. Handle LMS-specific response format
        6. Return standardized response
    """
    pass

# Add route to call this function:
@router.post("/courses/{course_id}/push-to-lms")
def push_course_to_lms(
    course_id: str,
    lms_token: str,  # From frontend via header or body
    assets: list,
    user_id: str = Depends(verify_token)
):
    """
    Export and push content directly to LMS platform
    """
    pass
```

### Frontend
```javascript
// FRONTEND: Update ExportAssetsModal to actually push to LMS
// File: frontend/src/components/ExportAssetsModal.js

const handleExport = async () => {
  // Get LMS token
  const lmsToken = localStorage.getItem("lms_token");
  
  if (!lmsToken) {
    // Redirect to login if token not found
    setError("LMS session expired. Please login again.");
    // Show login modal
    return;
  }
  
  // Call backend to push to LMS
  const response = await fetch(
    `${API_URL}/api/courses/${courseId}/push-to-lms`,
    {
      method: 'POST',
      headers: {
        'Authorization': `Bearer ${token}`,
        'X-LMS-Token': lmsToken,  // Custom header for LMS token
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({ assets: selectedAssets })
    }
  );
  
  // Handle response
  if (response.ok) {
    // Show success message
    // Close modal
  } else {
    // Handle error
    // If 401, token may be expired, show login modal
  }
};
```

## File Structure

```
course-copilot/
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── LMSLoginModal.js          ← New component
│       │   └── ExportAssetsModal.js      ← Existing, may need updates
│       └── layouts/
│           └── DashboardLayout.js        ← Updated to include login flow
└── backend/
    └── app/
        ├── routes/
        │   └── exportlms.py              ← Contains login and export routes
        ├── utils/
        │   └── lms_curl.py               ← LMS authentication utility
        └── config/
            └── settings.py               ← LMS_BASE_URL configuration
```

## Dependencies

### Frontend
- React
- Existing Modal component
- localStorage API

### Backend
- FastAPI
- requests library
- pydantic for request models

## Maintenance Notes

1. **Token Refresh:** Consider implementing token refresh mechanism if LMS tokens expire
2. **Multi-LMS Support:** Current implementation supports single LMS platform, may need extension for multiple platforms
3. **Offline Support:** Consider caching for offline export preparation
4. **Audit Logging:** Track export attempts for security and debugging

## Support

For issues or questions:
1. Check browser console for frontend errors
2. Check backend logs for API errors
3. Verify LMS_BASE_URL is correctly configured
4. Test LMS authentication separately
5. Ensure CORS is properly configured for LMS domain

