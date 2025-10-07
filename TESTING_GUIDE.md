# Testing Guide - LMS Export Frontend Flow

## ✅ Changes Made

### Frontend
1. **Fixed Header Component** - Changed from `AppHeader` to `DashboardHeader` which has the "Export to LMS" button
2. **Added LMSLoginModal** - New login modal component
3. **Updated Flow** - Click Export → Login Modal → Export Modal

### Backend
1. **Added Mock Mode** - Backend now returns a mock response when `LMS_BASE_URL` is not configured
2. **No Configuration Needed** - You can test the frontend flow without setting up LMS connection

## 🚀 How to Test

### 1. Start the Backend
```bash
cd backend
# Activate virtual environment if needed
# source venv/bin/activate (Mac/Linux)
# venv\Scripts\activate (Windows)

uvicorn app.main:app --reload
```

### 2. Start the Frontend
```bash
cd frontend
npm start
```

### 3. Test the Flow

1. **Login to your application** (with your regular course-copilot credentials)

2. **Navigate to the Dashboard page**

3. **Look for the "Export to LMS" button** in the header (blue button with upload icon)
   
4. **Click "Export to LMS"**
   - ✅ The LMS Login Modal should appear
   - ✅ You should see a yellow warning box saying "DEVELOPMENT MODE"

5. **Enter any email and password**
   - Can use test@example.com / password123
   - Or any other credentials (they won't be validated in mock mode)

6. **Click "Login to LMS"**
   - ✅ Should show loading spinner
   - ✅ Should close the login modal
   - ✅ Should automatically open the Export Assets Modal
   - ✅ Check browser console - should show "Running in MOCK MODE"

7. **Check localStorage**
   - Open browser DevTools (F12)
   - Go to Application → Local Storage
   - ✅ Should see `lms_token` with value like "mock_lms_token_for_testing_..."
   - ✅ Should see `lms_user` with mock user data

8. **In Export Assets Modal**
   - Select some assets
   - Click Export
   - ✅ Should download a JSON file with formatted assets

## 🔍 What to Look For

### Success Indicators ✅
- [ ] "Export to LMS" button visible in Dashboard header
- [ ] Clicking button opens LMS Login Modal
- [ ] Login Modal shows yellow "DEVELOPMENT MODE" warning
- [ ] Any email/password works (mock mode)
- [ ] Loading spinner appears during login
- [ ] Login modal closes on success
- [ ] Export Assets Modal opens automatically after login
- [ ] Console shows "Running in MOCK MODE" message
- [ ] localStorage has `lms_token` and `lms_user`

### Visual Check
The header should look like this:
```
Course Copilot [Grid][List][Settings][Export to LMS][Logout]
                                      ^^^^^^^^^^^^^^
                                      Blue button
```

## 🐛 Troubleshooting

### "Export to LMS" button not visible
- **Check:** Are you on the Dashboard page?
- **Check:** Is the DashboardHeader component loading?
- **Solution:** Check browser console for errors

### Modal doesn't open when clicking Export
- **Check:** Browser console for errors
- **Check:** React DevTools for state changes
- **Solution:** Refresh the page and try again

### "Authorization failed" or 401 error
- **Check:** Are you logged into the course-copilot app?
- **Check:** Is there a valid token in localStorage?
- **Solution:** Logout and login again

### Backend errors
- **Check:** Is backend running on port 8000?
- **Check:** Backend console for error messages
- **Solution:** Restart backend server

### Frontend won't compile
- **Check:** Run `npm install` to ensure all dependencies
- **Check:** Look for missing imports
- **Solution:** Check console for specific error

## 📝 Testing Checklist

Use this checklist to verify everything works:

- [ ] Backend starts without errors
- [ ] Frontend starts without errors
- [ ] Can login to course-copilot application
- [ ] Dashboard page loads
- [ ] "Export to LMS" button is visible
- [ ] Clicking button opens LMS Login Modal
- [ ] Modal has email and password fields
- [ ] Modal has yellow "DEVELOPMENT MODE" warning
- [ ] Password field has show/hide toggle
- [ ] Can enter email and password
- [ ] "Login to LMS" button is clickable
- [ ] Clicking login shows loading spinner
- [ ] Login succeeds with any credentials
- [ ] Login modal closes automatically
- [ ] Export Assets Modal opens automatically
- [ ] localStorage has `lms_token` stored
- [ ] localStorage has `lms_user` stored
- [ ] Console shows mock mode message
- [ ] Can select assets in Export Modal
- [ ] Can export selected assets

## 🎯 Expected Console Output

### Browser Console (Frontend)
```
⚠️ Running in MOCK MODE - LMS_BASE_URL not configured in backend
LMS login successful: {message: "Successfully logged into LMS (MOCK MODE...)", data: {...}}
```

### Backend Console
```
INFO: Request: POST /api/login-lms
WARNING: LMS_BASE_URL not configured. Returning mock response for user abc12345
INFO: Response: 200 - 0.005s
```

## 🔄 Next Steps After Testing

Once you've verified the frontend flow works:

1. **When you get LMS_BASE_URL:**
   - Add `LMS_BASE_URL=https://your-lms-platform.com` to backend `.env`
   - Restart backend
   - Backend will switch from mock mode to real LMS authentication

2. **Update the info message:**
   - Remove the yellow warning in `LMSLoginModal.js`
   - Replace with blue info box about secure transmission

3. **Test with real LMS:**
   - Use actual LMS credentials
   - Verify connection to real LMS platform
   - Check that real token is returned

## 💡 Tips

- **Keep browser DevTools open** to see console messages and network requests
- **Check Network tab** to see API calls to `/api/login-lms`
- **Use React DevTools** to inspect component state
- **Check localStorage** to verify tokens are stored correctly

## 📞 If You Need Help

Check these files for implementation details:
- `frontend/src/components/LMSLoginModal.js` - Login modal component
- `frontend/src/layouts/DashboardLayout.js` - Dashboard with modal state
- `backend/app/routes/exportlms.py` - Backend login endpoint
- `LMS_EXPORT_FLOW.md` - Complete flow documentation

---

**Ready to test?** Start your servers and follow the testing steps above! 🚀

