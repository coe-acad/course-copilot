# LMS Export Flow - Quick Reference

## 🎯 Complete User Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                                                                     │
│  1️⃣  DASHBOARD                                                      │
│     User clicks "Export to LMS" button                             │
│                                                                     │
│     ↓                                                               │
│                                                                     │
│  2️⃣  LMS LOGIN MODAL                                                │
│     User enters: username, password, LMS URL                       │
│     Backend: POST /api/login-lms                                   │
│     Stores: lms_token in localStorage                              │
│                                                                     │
│     ↓                                                               │
│                                                                     │
│  3️⃣  LMS COURSES PAGE (Export Mode)                                │
│     Backend: GET /api/lms/courses                                  │
│     Shows: List of all LMS courses                                 │
│     Options:                                                        │
│       • Select existing course (click card)                        │
│       • Create new course (click button)                           │
│     Visual: Selected course highlighted with ✓                     │
│                                                                     │
│     ↓                                                               │
│                                                                     │
│  4️⃣  DASHBOARD → EXPORT ASSETS MODAL                               │
│     Shows: Selected course banner at top                           │
│           OR "Creating New Course" banner                          │
│     User: Selects which assets to export                           │
│     Backend: POST /api/courses/{id}/export-lms                     │
│     Data: assets + lms_course_id + lms_course_info                 │
│                                                                     │
│     ↓                                                               │
│                                                                     │
│  5️⃣  SUCCESS                                                        │
│     Assets exported to LMS course                                  │
│     User returns to Dashboard                                      │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

## 🔄 Navigation Flow

```
Dashboard (/)
    │
    ├─[Click "Export to LMS"]
    │
    ↓
LMS Login Modal
    │
    ├─[Enter credentials & login]
    │
    ↓
LMS Courses Page (/lms-courses?fromExport=true)
    │
    ├─[Select course OR create new]
    │
    ↓
Dashboard (/)
    │
    ├─[Auto-open Export Assets Modal]
    │   └─Shows selected course
    │
    ├─[Select assets]
    │
    ├─[Click "Export"]
    │
    ↓
Backend processes export
    │
    ↓
Success → Back to Dashboard
```

## 📊 State Passed Between Components

### Dashboard → LMS Courses
```javascript
navigate('/lms-courses', {
  state: {
    fromExport: true,        // Triggers export mode
    assets: allAssets        // All available assets
  }
});
```

### LMS Courses → Dashboard
```javascript
navigate('/dashboard', {
  state: {
    showExportModal: true,           // Open modal immediately
    selectedLMSCourse: course,       // Selected course object
    assetsToExport: assetsToExport   // Assets to export
  }
});
```

## 🎨 Visual States

### 1. Dashboard - Initial
```
┌──────────────────────────────────┐
│ [Settings] [Export to LMS] 👤    │
├──────────────────────────────────┤
│                                  │
│  Curriculum     Assessments      │
│  [Course Outcomes] [Quiz 1]      │
│  [Modules]         [Assignment]  │
│                                  │
└──────────────────────────────────┘
```

### 2. LMS Login Modal
```
┌──────────────────────────────────┐
│  🔐 Login to LMS                 │
│                                  │
│  Email/Username: [________]      │
│  Password:       [________]      │
│  LMS URL:        [________]      │
│                                  │
│          [Cancel] [Login]        │
└──────────────────────────────────┘
```

### 3. LMS Courses (Export Mode)
```
┌──────────────────────────────────┐
│ Select LMS Course for Export     │
├──────────────────────────────────┤
│ ┌──────────────────────────────┐ │
│ │ ➕ Create New Course in LMS  │ │
│ └──────────────────────────────┘ │
│ [Search: _________________]      │
│ ┌──────────────────────────────┐ │
│ │ CS101: Intro to ML      ✓    │ │ ← Selected
│ │ Dr. Smith • 45 students      │ │
│ └──────────────────────────────┘ │
│ ┌──────────────────────────────┐ │
│ │ CS102: Advanced ML           │ │
│ │ Dr. Jones • 32 students      │ │
│ └──────────────────────────────┘ │
├──────────────────────────────────┤
│     [Cancel] [Continue to Export→]│
└──────────────────────────────────┘
```

### 4. Export Assets Modal
```
┌──────────────────────────────────┐
│ ┌──────────────────────────────┐ │
│ │ 📚 Exporting to LMS Course:  │ │
│ │ CS101: Intro to ML           │ │
│ └──────────────────────────────┘ │
│                                  │
│ Export Assets     3 selected / 8 │
│ [Search] [☑ Select all]          │
│ ┌──────────────────────────────┐ │
│ │ Curriculum                   │ │
│ │ ☑ Course Outcomes            │ │
│ │ ☑ Modules                    │ │
│ │                              │ │
│ │ Assessments                  │ │
│ │ ☑ Quiz 1                     │ │
│ │ ☐ Assignment 1               │ │
│ └──────────────────────────────┘ │
│          [Cancel] [Export (3)]   │
└──────────────────────────────────┘
```

## 🔌 Backend API Calls

### Call 1: LMS Login
```
POST /api/login-lms
Request: { username, password, lms_url }
Response: { lms_token, user }
Storage: localStorage.setItem('lms_token', token)
```

### Call 2: Get LMS Courses
```
GET /api/lms/courses
Headers: { 
  Authorization: Bearer <user_token>,
  X-LMS-Token: <lms_token>
}
Response: { courses: [...] }
```

### Call 3: Export Assets
```
POST /api/courses/{id}/export-lms
Headers: { Authorization: Bearer <user_token> }
Body: {
  asset_names: [...],
  asset_type: [...],
  lms_course_id: "...",    // or null
  lms_course_name: "...",
  lms_course_code: "..."
}
Response: { success, data }
```

## ✅ Key Features

| Feature | Description |
|---------|-------------|
| **Course Selection** | Choose destination before export |
| **Create New Course** | Option to create fresh course in LMS |
| **Visual Feedback** | Selected course clearly highlighted |
| **Asset Selection** | Choose exactly what to export |
| **Context Awareness** | Course info shown throughout |
| **Cancellable** | Can abort at any step |
| **Error Handling** | Friendly messages at each stage |

## 🎯 User Benefits

1. **Control**: Choose exactly where content goes
2. **Safety**: See destination before exporting
3. **Flexibility**: Export to existing OR create new
4. **Clarity**: Always know what's being exported where
5. **Efficiency**: Streamlined 5-step process

## 📱 Responsive Design

All components work on:
- ✅ Desktop (1920x1080+)
- ✅ Laptop (1366x768+)
- ✅ Tablet (768x1024)
- ✅ Mobile (375x667+)

## 🚀 Performance

- **Fast Navigation**: React Router instant transitions
- **Optimized Loading**: Shows spinners during API calls
- **State Preservation**: No data loss between pages
- **Local Storage**: LMS token persists across sessions

## 🔐 Security

- **Token Storage**: LMS token in localStorage
- **Token Validation**: Backend validates on each request
- **Session Expiry**: Handles expired tokens gracefully
- **HTTPS**: All API calls use secure connections

## 📚 Related Files

- `frontend/src/pages/LMSCourses.js` - Courses page
- `frontend/src/pages/Dashboard.js` - Dashboard with export
- `frontend/src/components/ExportAssetsModal.js` - Export modal
- `frontend/src/components/LMSLoginModal.js` - Login modal
- `LMS_EXPORT_FLOW_UPDATED.md` - Detailed documentation
- `LMS_COURSES_FEATURE.md` - Courses page documentation

---

**Quick Start Testing**:
1. Go to Dashboard
2. Click "Export to LMS"
3. Enter dummy credentials (backend not required for UI testing)
4. See course selection page
5. Select a course or click "Create New"
6. See export modal with course info
7. Select assets and export

**Status**: ✅ Ready for Backend Integration

