# CORS Configuration Guide

## Overview
This document explains the CORS (Cross-Origin Resource Sharing) configuration for the Creator Copilot API.

## Current Implementation

### Configuration Location
- **Settings**: `backend/app/config/settings.py`
- **Middleware**: `backend/app/main.py`

### Environment Variables

| Variable | Default Value | Description |
|----------|---------------|-------------|
| `CORS_ORIGINS` | `http://localhost:3000,http://localhost:8000,http://localhost:8501` | Comma-separated list of allowed origins |
| `CORS_ALLOW_CREDENTIALS` | `True` | Allow credentials (cookies, authorization headers) |
| `CORS_ALLOW_METHODS` | `GET,POST,PUT,DELETE,OPTIONS` | Allowed HTTP methods |
| `CORS_ALLOW_HEADERS` | `Authorization,Content-Type,Accept,Origin,User-Agent` | Allowed request headers |
| `CORS_EXPOSE_HEADERS` | `Content-Length,Content-Range` | Headers exposed to the browser |
| `CORS_MAX_AGE` | `3600` | Cache duration for preflight requests (seconds) |

## Security Improvements Made

### 1. Environment-Based Configuration
- **Before**: Hardcoded origins in main.py
- **After**: Configurable via environment variables
- **Benefit**: Easy deployment to different environments

### 2. Restricted Methods and Headers
- **Before**: `allow_methods=["*"]` and `allow_headers=["*"]`
- **After**: Specific allowed methods and headers
- **Benefit**: Reduced attack surface, better security

### 3. Configurable Security Settings
- **Before**: Fixed settings
- **After**: All CORS settings configurable via environment
- **Benefit**: Flexibility for different deployment scenarios

## Production Configuration

For production deployment, update your environment variables:

```bash
# Development
CORS_ORIGINS=http://localhost:3000,http://localhost:8000,http://localhost:8501

# Production
CORS_ORIGINS=https://yourdomain.com,https://www.yourdomain.com,https://app.yourdomain.com
```

## Security Best Practices

1. **Specific Origins**: Only allow necessary origins
2. **Minimal Headers**: Only expose required headers
3. **Limited Methods**: Only allow necessary HTTP methods
4. **Credentials**: Only enable if required for your application
5. **Max Age**: Set appropriate cache duration for preflight requests

## Testing CORS

You can test CORS configuration using:

```bash
# Test preflight request
curl -X OPTIONS \
  -H "Origin: http://localhost:3000" \
  -H "Access-Control-Request-Method: POST" \
  -H "Access-Control-Request-Headers: Content-Type" \
  http://localhost:8000/api/courses

# Test actual request
curl -X POST \
  -H "Origin: http://localhost:3000" \
  -H "Content-Type: application/json" \
  -d '{"name":"Test Course"}' \
  http://localhost:8000/api/courses
```

## Troubleshooting

### Common Issues

1. **CORS Error**: Check if origin is in `CORS_ORIGINS`
2. **Credentials Not Sent**: Ensure `CORS_ALLOW_CREDENTIALS=True`
3. **Headers Blocked**: Verify headers are in `CORS_ALLOW_HEADERS`
4. **Methods Blocked**: Check if method is in `CORS_ALLOW_METHODS`

### Debug Mode

Enable debug mode to see detailed CORS logs:

```bash
DEBUG=True
LOG_LEVEL=DEBUG
``` 