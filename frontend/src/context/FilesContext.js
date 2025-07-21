import React, { createContext, useContext, useState } from "react";

const FilesContext = createContext();

export function FilesProvider({ children }) {
  const [files, setFiles] = useState([]);

  // backend integration
  const addFiles = (newFiles) => {
    setFiles((prev) => [...prev, ...newFiles]);
  };

  // backend integration
  const updateFileChecked = (name, checked) => {
    setFiles((prev) => prev.map(f => f.name === name ? { ...f, checked } : f));
  };

  // backend integration
  const setAllChecked = (checked) => {
    setFiles((prev) => prev.map(f => ({ ...f, checked })));
  };

  return (
    <FilesContext.Provider value={{ files, addFiles, updateFileChecked, setAllChecked }}>
      {children}
    </FilesContext.Provider>
  );
}

export function useFilesContext() {
  return useContext(FilesContext);
} 