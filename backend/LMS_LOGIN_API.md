# LMS Login API Documentation

## Overview
This API endpoint allows you to authenticate with an external LMS (Learning Management System) platform using email and password credentials.

## Endpoint

### POST `/api/login-lms`

Authenticate with the LMS platform.

#### Request Headers
- `Authorization: Bearer <token>` - Your authentication token

#### Request Body
```json
{
  "email": "user@example.com",
  "password": "userpassword123",
  "lms_base_url": "https://lms.example.com"
}
```

#### Parameters
- `email` (string, required): User's email for the LMS platform
- `password` (string, required): User's password for the LMS platform
- `lms_base_url` (string, required): Base URL of the LMS platform (without trailing slash)

#### Success Response (200 OK)
```json
{
  "message": "Successfully logged into LMS",
  "data": {
    "token": "jwt_token_from_lms",
    "user": {
      "id": "user_id",
      "email": "user@example.com",
      "name": "User Name"
    }
  }
}
```

#### Error Responses

**400 Bad Request** - Missing required fields
```json
{
  "detail": "Email and password are required"
}
```

**401 Unauthorized** - Invalid credentials
```json
{
  "detail": "LMS authentication failed"
}
```

**408 Request Timeout** - LMS server timeout
```json
{
  "detail": "Request timeout - LMS server took too long to respond"
}
```

**503 Service Unavailable** - Connection error
```json
{
  "detail": "Connection error - Could not connect to LMS server"
}
```

**500 Internal Server Error** - Unexpected error
```json
{
  "detail": "Internal server error: <error_message>"
}
```

## Frontend Integration Example

### Using Fetch API
```javascript
async function loginToLMS(email, password, lmsBaseUrl) {
  try {
    const response = await fetch('http://localhost:8000/api/login-lms', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${yourAuthToken}`
      },
      body: JSON.stringify({
        email: email,
        password: password,
        lms_base_url: lmsBaseUrl
      })
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Login failed');
    }

    const data = await response.json();
    console.log('Login successful:', data);
    return data;
  } catch (error) {
    console.error('LMS login error:', error.message);
    throw error;
  }
}

// Usage
loginToLMS('user@example.com', 'password123', 'https://lms.example.com')
  .then(result => {
    console.log('LMS Token:', result.data.token);
  })
  .catch(error => {
    console.error('Failed to login:', error);
  });
```

### Using Axios
```javascript
import axios from 'axios';

async function loginToLMS(email, password, lmsBaseUrl) {
  try {
    const response = await axios.post('http://localhost:8000/api/login-lms', {
      email: email,
      password: password,
      lms_base_url: lmsBaseUrl
    }, {
      headers: {
        'Authorization': `Bearer ${yourAuthToken}`
      }
    });

    console.log('Login successful:', response.data);
    return response.data;
  } catch (error) {
    if (error.response) {
      console.error('LMS login error:', error.response.data.detail);
    } else {
      console.error('Network error:', error.message);
    }
    throw error;
  }
}
```

## Backend Implementation Details

### File: `backend/app/utils/lms_curl.py`
Contains the `login_to_lms()` function that:
1. Constructs the full LMS authentication URL
2. Sends a POST request with email and password
3. Handles various error scenarios (timeout, connection error, HTTP errors)
4. Returns a structured response with success status and data

### File: `backend/app/routes/exportlms.py`
Contains the `/login-lms` route that:
1. Validates the request body
2. Calls the `login_to_lms()` utility function
3. Returns appropriate HTTP responses based on the result

## Testing

### Using cURL
```bash
curl --location 'http://localhost:8000/api/login-lms' \
--header 'Content-Type: application/json' \
--header 'Authorization: Bearer YOUR_AUTH_TOKEN' \
--data-raw '{
    "email": "user@example.com",
    "password": "password123",
    "lms_base_url": "https://lms.example.com"
}'
```

### Using HTTPie
```bash
http POST http://localhost:8000/api/login-lms \
    Authorization:"Bearer YOUR_AUTH_TOKEN" \
    email="user@example.com" \
    password="password123" \
    lms_base_url="https://lms.example.com"
```

## Security Considerations

1. **HTTPS Only**: Always use HTTPS in production to encrypt credentials in transit
2. **Token Storage**: Store the returned LMS token securely (e.g., in httpOnly cookies or secure storage)
3. **Error Messages**: Avoid exposing sensitive information in error messages
4. **Rate Limiting**: Consider implementing rate limiting to prevent brute force attacks
5. **Timeout**: The request has a 30-second timeout to prevent hanging connections

## Notes

- The actual response structure from the LMS may vary depending on the LMS platform being used
- The `lms_base_url` should not include a trailing slash
- The function automatically appends `/api/v1/auth/signin` to the base URL
- All requests are logged for debugging purposes

