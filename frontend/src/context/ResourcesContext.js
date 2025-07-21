import React, { createContext, useContext, useState, useCallback, useMemo, useEffect } from 'react';
import { getAssetResources, uploadCourseResources, uploadAssetResources, addCheckedInFilesToThread } from '../services/resources';

const ResourcesContext = createContext();

export const useResources = () => {
  const context = useContext(ResourcesContext);
  if (!context) {
    throw new Error('useResources must be used within a ResourcesProvider');
  }
  return context;
};

// Utility: File -> DataURL (async)
function fileToDataURL(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = (e) => resolve(e.target.result);
    reader.onerror = (e) => reject(e);
    reader.readAsDataURL(file);
  });
}
// Utility: DataURL -> File
function dataURLtoFile(dataurl, filename, filetype) {
  const arr = dataurl.split(','), mime = arr[0].match(/:(.*?);/)[1], bstr = atob(arr[1]), n = bstr.length, u8arr = new Uint8Array(n);
  for (let i = 0; i < n; i++) u8arr[i] = bstr.charCodeAt(i);
  return new File([u8arr], filename, { type: filetype || mime });
}
function getPendingKey(courseId) {
  return `pendingResources_${courseId}`;
}
// Helper to list files in localStorage for a course (browser localStorage, not backend)
function getLocalCourseFiles(courseId) {
  // New format: { folderName: [fileObj, ...], ... }
  const key = `courseFiles_${courseId}`;
  const saved = localStorage.getItem(key);
  if (!saved) return {};
  try {
    const parsed = JSON.parse(saved);
    // If old format (array), convert to {"root": array}
    if (Array.isArray(parsed)) {
      return { root: parsed };
    }
    return parsed;
  } catch {
    return {};
  }
}

export const ResourcesProvider = ({ children }) => {
  const [resources, setResources] = useState({});
  const [pendingFiles, setPendingFiles] = useState([]); // [{file, courseId}]
  const [loading, setLoading] = useState({});
  const [error, setError] = useState({});
  const [currentCourseId, setCurrentCourseId] = useState(null);
  const [openThreadId, setOpenThreadId] = useState(null);
  // Track all known thread IDs for the course
  const [threadIds, setThreadIds] = useState([]);
  // Track checked-in and checked-out fileNames in state
  const [checkedInFiles, setCheckedInFiles] = useState(() => {
    const courseId = localStorage.getItem('currentCourseId');
    const saved = localStorage.getItem(`checkedInFiles_${courseId}`);
    return saved ? JSON.parse(saved) : [];
  });
  const [checkedOutFiles, setCheckedOutFiles] = useState(() => {
    const courseId = localStorage.getItem('currentCourseId');
    const saved = localStorage.getItem(`checkedOutFiles_${courseId}`);
    return saved ? JSON.parse(saved) : [];
  });

  // Persist checkedInFiles and checkedOutFiles in localStorage per courseId
  useEffect(() => {
    const courseId = localStorage.getItem('currentCourseId');
    if (courseId) {
      localStorage.setItem(`checkedInFiles_${courseId}`, JSON.stringify(checkedInFiles));
      localStorage.setItem(`checkedOutFiles_${courseId}`, JSON.stringify(checkedOutFiles));
    }
  }, [checkedInFiles, checkedOutFiles]);

  // Helper to sync assistant-level resources for all threads
  const syncAssistantResources = useCallback(async (courseId) => {
    // Always sync for all known threads for this course
    for (const threadId of threadIds) {
      if (threadId) {
        try {
          await addCheckedInFilesToThread(courseId, threadId);
        } catch (e) {
          // Ignore errors
        }
      }
    }
  }, [threadIds]);

  // Whenever pendingFiles change, sync assistant-level resources
  useEffect(() => {
    if (currentCourseId) {
      syncAssistantResources(currentCourseId);
    }
  }, [pendingFiles, currentCourseId, syncAssistantResources]);

  // On mount and whenever courseId or openThreadId changes, load and merge course-level and asset-level resources
  useEffect(() => {
    const courseId = localStorage.getItem('currentCourseId');
    if (!courseId) return;
    const threadId = openThreadId;
    async function loadAllResources() {
      let courseFiles = getLocalCourseFiles(courseId);
      // Flatten all files from all folders
      let courseFilesFlat = Object.values(courseFiles).flat();
      let assetFiles = [];
      // Try to fetch asset-level resources if threadId is available
      if (threadId) {
        try {
          assetFiles = await getAssetResources(courseId, threadId);
        } catch (e) {
          assetFiles = [];
        }
      }
      // Merge and deduplicate by fileId or fileName
      const allFiles = [...courseFilesFlat, ...assetFiles].filter((file, idx, arr) => {
        if (file.fileId) {
          return arr.findIndex(f => f.fileId === file.fileId) === idx;
        }
        return arr.findIndex(f => f.fileName === file.fileName) === idx;
      });
      setResources(prev => ({ ...prev, [courseId]: { root: allFiles } }));
    }
    loadAllResources();
  }, [currentCourseId, openThreadId]);

  // When adding a new file, also update localStorage (now supports folders)
  const addResource = useCallback((courseId, resource, folder = "root") => {
    setResources(prev => {
      const prevCourse = prev[courseId] || {};
      const updatedFolder = [...(prevCourse[folder] || []), resource];
      const updated = {
        ...prev,
        [courseId]: {
          ...prevCourse,
          [folder]: updatedFolder
        }
      };
      // Save to localStorage in folder format
      localStorage.setItem(`courseFiles_${courseId}`, JSON.stringify(updated[courseId]));
      return updated;
    });
  }, []);

  // When removing a file, also update localStorage (now supports folders)
  const removeResource = useCallback((courseId, fileId, folder = "root") => {
    setResources(prev => {
      const prevCourse = prev[courseId] || {};
      const updatedFolder = (prevCourse[folder] || []).filter(r => r.fileId !== fileId);
      const updated = {
        ...prev,
        [courseId]: {
          ...prevCourse,
          [folder]: updatedFolder
        }
      };
      // Save to localStorage in folder format
      localStorage.setItem(`courseFiles_${courseId}`, JSON.stringify(updated[courseId]));
      return updated;
    });
  }, []);

  // Update loadResources to support folder format
  const loadResources = useCallback(async (courseId) => {
    if (!courseId) return;
    setLoading(prev => ({ ...prev, [courseId]: true }));
    setError(prev => ({ ...prev, [courseId]: null }));
    try {
      // Load from localStorage only
      const filesByFolder = getLocalCourseFiles(courseId);
      setResources(prev => ({ ...prev, [courseId]: filesByFolder }));
    } catch (err) {
      setError(prev => ({
        ...prev,
        [courseId]: err.message || 'Failed to load resources'
      }));
    } finally {
      setLoading(prev => ({ ...prev, [courseId]: false }));
    }
  }, []);

  // When committing files, also sync assistant-level resources
  const commitPendingFiles = useCallback(async (courseId, threadId = null) => {
    const filesToUpload = pendingFiles.filter(f => f.courseId === courseId).map(f => f.file);
    if (filesToUpload.length === 0) return { success: false, message: 'No pending files to upload' };
    let response;
    try {
      if (threadId) {
        response = await uploadAssetResources(courseId, threadId, filesToUpload);
      } else {
        response = await uploadCourseResources(courseId, filesToUpload);
      }
      setPendingFiles(prev => prev.filter(f => f.courseId !== courseId));
      const key = getPendingKey(courseId);
      localStorage.removeItem(key);
      await loadResources(courseId);
      await syncAssistantResources(courseId);
      return { success: true, response };
    } catch (err) {
      return { success: false, message: err.message };
    }
  }, [pendingFiles, loadResources, syncAssistantResources]);

  // Load pending files from localStorage on mount or courseId change
  useEffect(() => {
    const courseId = localStorage.getItem('currentCourseId');
    setCurrentCourseId(courseId);
    if (!courseId) return;
    const key = getPendingKey(courseId);
    const saved = localStorage.getItem(key);
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        // Reconstruct File objects from DataURL
        const files = parsed.map(f => ({
          file: dataURLtoFile(f.fileData, f.fileName, f.fileType),
          courseId: f.courseId
        }));
        setPendingFiles(files);
      } catch (e) {
        setPendingFiles([]);
      }
    } else {
      setPendingFiles([]);
    }
  }, []);

  // Save pending files to localStorage whenever they change
  useEffect(() => {
    if (!currentCourseId) return;
    const key = getPendingKey(currentCourseId);
    // Only save serializable data (not File objects)
    const save = async () => {
      const serializable = await Promise.all(pendingFiles.map(async f => ({
        fileName: f.file.name,
        fileType: f.file.type,
        fileData: await fileToDataURL(f.file),
        courseId: f.courseId
      })));
      localStorage.setItem(key, JSON.stringify(serializable));
    };
    save();
  }, [pendingFiles, currentCourseId]);

  const updateResource = useCallback((courseId, fileId, updates) => {
    setResources(prev => ({
      ...prev,
      [courseId]: Object.keys(prev[courseId]).reduce((acc, folder) => {
        acc[folder] = prev[courseId][folder].map(resource =>
          resource.fileId === fileId
            ? { ...resource, ...updates }
            : resource
        );
        return acc;
      }, {})
    }));
  }, []);

  // Check in/out logic by fileName (useCallback for stable reference)
  const checkoutResource = useCallback((fileName) => {
    setCheckedInFiles(prev => prev.filter(name => name !== fileName));
    setCheckedOutFiles(prev => prev.includes(fileName) ? prev : [...prev, fileName]);
    setTimeout(() => {
      const updated = checkedInFiles.filter(name => name !== fileName);
      console.log('Checked-in files:', updated);
    }, 0);
  }, [checkedInFiles]);

  // Update getAllResources to flatten folder structure for UI (optionally grouped)
  const getAllResources = useCallback((courseId, groupByFolder = false) => {
    const courseRes = resources[courseId] || {};
    if (groupByFolder) return courseRes;
    // Flatten all folders into a single array
    return Object.values(courseRes).flat();
  }, [resources]);

  const getResources = useCallback((courseId) => {
    return resources[courseId] || [];
  }, [resources]);

  const isLoading = useCallback((courseId) => {
    return loading[courseId] || false;
  }, [loading]);

  const getError = useCallback((courseId) => {
    return error[courseId] || null;
  }, [error]);

  const clearError = useCallback((courseId) => {
    setError(prev => ({ ...prev, [courseId]: null }));
  }, []);

  const refreshResources = useCallback(async (courseId) => {
    if (!courseId) return;
    setLoading(prev => ({ ...prev, [courseId]: true }));
    setError(prev => ({ ...prev, [courseId]: null }));
    try {
      // Load from localStorage only
      const files = getLocalCourseFiles(courseId);
      setResources(prev => ({ ...prev, [courseId]: files }));
    } catch (err) {
      setError(prev => ({
        ...prev,
        [courseId]: err.message || 'Failed to refresh resources'
      }));
    } finally {
      setLoading(prev => ({ ...prev, [courseId]: false }));
    }
  }, []);

  // Expose setOpenThreadId and a way to register thread IDs
  const registerThreadId = useCallback((threadId) => {
    setThreadIds(prev => prev.includes(threadId) ? prev : [...prev, threadId]);
  }, []);

  // When creating checked-in/checked-out lists, include openThreadId for accuracy
  // (Assume this is used in the UI logic, so just expose openThreadId)

  // Pending file/session logic
  const addPendingFiles = useCallback(async (files) => {
    const courseId = localStorage.getItem('currentCourseId');
    if (!courseId) return;
    const fileObjs = files.map(f => ({ file: f, courseId }));
    setPendingFiles(prev => ([...prev, ...fileObjs]));
  }, []);

  const removePendingFile = useCallback((fileName) => {
    setPendingFiles(prev => prev.filter(f => f.file.name !== fileName));
  }, []);

  // Add and immediately commit files (auto-upload)
  const addAndCommitFiles = useCallback(async (files, courseId, threadId = null) => {
    await addPendingFiles(files);
    return await commitPendingFiles(courseId, threadId);
  }, [addPendingFiles, commitPendingFiles]);

  const value = useMemo(() => ({
    resources,
    pendingFiles,
    loadResources,
    updateResource,
    addResource,
    removeResource,
    addPendingFiles,
    removePendingFile,
    commitPendingFiles,
    addAndCommitFiles,
    getResources,
    getAllResources,
    isLoading,
    getError,
    clearError,
    refreshResources,
    setOpenThreadId,
    openThreadId,
    registerThreadId,
    checkoutResource
  }), [
    resources,
    pendingFiles,
    loadResources,
    updateResource,
    addResource,
    removeResource,
    addPendingFiles,
    removePendingFile,
    commitPendingFiles,
    addAndCommitFiles,
    getResources,
    getAllResources,
    isLoading,
    getError,
    clearError,
    refreshResources,
    setOpenThreadId,
    openThreadId,
    registerThreadId,
    checkoutResource
  ]);

  return (
    <ResourcesContext.Provider value={value}>
      {children}
    </ResourcesContext.Provider>
  );
}; 