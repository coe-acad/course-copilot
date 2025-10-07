# LMS Courses Feature

## Overview
This feature allows users to view their courses from the Learning Management System (LMS) directly within the Course Copilot application. Users can browse, search, and view course details in both grid and list views.

## User Flow

1. **Access**: User clicks "📚 View LMS Courses" button in the Dashboard header
2. **Authentication**: System uses the LMS token stored during LMS login
3. **Display**: Courses are fetched and displayed in either grid or list view
4. **Search**: Users can search courses by name, code, or instructor
5. **Refresh**: Users can manually refresh the course list

## Files Created/Modified

### New Files
- `/frontend/src/pages/LMSCourses.js` - Main LMS Courses page component

### Modified Files
- `/frontend/src/App.js` - Added route for `/lms-courses`
- `/frontend/src/components/header/Header.js` - Added `onViewLMSCourses` prop and button
- `/frontend/src/pages/Dashboard.js` - Added navigation to LMS Courses page

## Frontend Implementation

### Route
```javascript
<Route path="/lms-courses" element={<LMSCourses />} />
```

### Navigation
From Dashboard header, users can click "📚 View LMS Courses" to navigate to `/lms-courses`

### Features
- **Grid View**: Cards showing course details with hover effects
- **List View**: Tabular format for detailed course information
- **Search**: Filter courses by name, code, or instructor
- **Refresh**: Manual refresh button to reload courses
- **Loading State**: Spinner animation while fetching
- **Error Handling**: User-friendly error messages with retry option
- **Responsive Design**: Adapts to different screen sizes

### UI Components

#### Course Card (Grid View)
- Course name and code
- Status badge (active/archived/draft)
- Description (truncated to 3 lines)
- Instructor information
- Enrollment count
- Start and end dates

#### Course Table (List View)
- Course name (clickable)
- Course code
- Instructor
- Number of students
- Start date
- Status badge

## Backend Integration Required

### Endpoint: `GET /api/lms/courses`

#### Request
```http
GET /api/lms/courses HTTP/1.1
Authorization: Bearer <user_auth_token>
X-LMS-Token: <lms_token_from_login>
Content-Type: application/json
```

#### Expected Success Response (200)
```json
{
  "success": true,
  "courses": [
    {
      "id": "course_id_123",
      "name": "Introduction to Machine Learning",
      "code": "CS101",
      "description": "Course description here...",
      "start_date": "2024-01-15",
      "end_date": "2024-05-20",
      "enrollment_count": 45,
      "status": "active",
      "instructor": "Dr. Jane Smith",
      "created_at": "2024-01-01T00:00:00Z",
      "updated_at": "2024-01-10T00:00:00Z"
    }
  ]
}
```

#### Expected Error Responses
- **401 Unauthorized**: `{ "detail": "LMS token expired or invalid" }`
- **403 Forbidden**: `{ "detail": "Insufficient permissions" }`
- **500 Server Error**: `{ "detail": "Failed to fetch courses from LMS" }`

### Backend Implementation Steps

1. **Validate LMS Token**
   - Extract LMS token from `X-LMS-Token` header
   - Verify token validity and expiration
   - Return 401 if invalid or expired

2. **Call LMS Platform API**
   - Make authenticated request to LMS platform
   - Example: `GET {LMS_BASE_URL}/api/v1/courses`
   - Include authorization header: `Authorization: Bearer {lms_token}`

3. **Transform Response**
   - Map LMS response fields to expected format
   - Ensure all required fields are present
   - Handle optional fields gracefully

4. **Filter & Sort**
   - Filter courses based on user permissions
   - Sort courses by relevant criteria (e.g., start_date)

5. **Error Handling**
   - Catch LMS API errors
   - Provide user-friendly error messages
   - Log errors for debugging

6. **Optional Enhancements**
   - Implement caching to reduce LMS API calls
   - Add pagination for large course lists
   - Include course thumbnails/images
   - Add course statistics (assignments, modules, etc.)

## Testing

### Manual Testing Checklist
- [ ] Navigate to LMS Courses page from Dashboard
- [ ] Verify loading spinner appears while fetching
- [ ] Verify courses display correctly in grid view
- [ ] Switch to list view and verify table display
- [ ] Test search functionality with various queries
- [ ] Test refresh button
- [ ] Test error handling (invalid token, network error)
- [ ] Verify back button returns to Dashboard
- [ ] Test responsive design on different screen sizes

### Backend Testing
- [ ] Test with valid LMS token
- [ ] Test with expired LMS token
- [ ] Test with invalid LMS token
- [ ] Test with no LMS token
- [ ] Test LMS API connection failure
- [ ] Test with empty course list
- [ ] Test with large number of courses
- [ ] Test pagination (if implemented)

## Future Enhancements

1. **Course Details Page**: Click on a course to see detailed information
2. **Course Selection**: Select courses to import or sync with Course Copilot
3. **Course Creation**: Create new courses directly in LMS from Course Copilot
4. **Sync Status**: Show sync status between Course Copilot and LMS
5. **Course Import**: Import LMS course content into Course Copilot
6. **Bulk Actions**: Perform actions on multiple courses at once
7. **Advanced Filters**: Filter by date range, status, instructor, etc.
8. **Course Analytics**: Display course performance metrics
9. **Export Course Data**: Export course list to CSV/Excel

## Related Features

- **LMS Login Modal**: `/frontend/src/components/LMSLoginModal.js`
- **Export Assets Modal**: `/frontend/src/components/ExportAssetsModal.js`
- **LMS Export Flow**: See `frontend/LMS_EXPORT_FLOW.md`

## API Integration Notes

The frontend expects the backend to integrate with various LMS platforms such as:
- Canvas LMS
- Moodle
- Blackboard
- Google Classroom
- Custom LMS implementations

The backend should abstract the LMS-specific details and provide a consistent API interface to the frontend.

## Security Considerations

1. **Token Storage**: LMS token is stored in localStorage (consider more secure storage)
2. **Token Expiration**: Frontend handles 401 errors and prompts re-login
3. **HTTPS Required**: All LMS API calls should use HTTPS
4. **CORS**: Backend should handle CORS appropriately
5. **Rate Limiting**: Consider rate limiting LMS API calls

## Environment Variables

The frontend uses:
```javascript
process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000'
```

Backend should configure:
- `LMS_BASE_URL`: Base URL of the LMS platform
- `LMS_API_VERSION`: API version to use
- `LMS_CLIENT_ID`: OAuth client ID (if applicable)
- `LMS_CLIENT_SECRET`: OAuth client secret (if applicable)

