import React, { useState } from 'react';
import Modal from './Modal'; // Use your existing Modal component

export default function KnowledgeBaseSelectModal({ open, onClose, onGenerate, files }) {
  const [selected, setSelected] = useState([]);

  const handleToggle = (file) => {
    setSelected((prev) =>
      prev.includes(file) ? prev.filter(f => f !== file) : [...prev, file]
    );
  };

  const handleGenerate = () => {
    onGenerate(selected);
    setSelected([]); // Reset selection after generate
  };

  if (!open) return null;

  return (
    <Modal open={open} onClose={onClose}>
      <h2>Select Knowledge Base Files</h2>
      <ul style={{ maxHeight: 200, overflowY: 'auto', padding: 0 }}>
        {files.map(file => (
          <li key={file.id || file.fileName || file.name} style={{ listStyle: 'none', marginBottom: 8 }}>
            <label>
              <input
                type="checkbox"
                checked={selected.includes(file)}
                onChange={() => handleToggle(file)}
              />
              {file.name || file.fileName || file.title}
            </label>
          </li>
        ))}
      </ul>
      <div style={{ marginTop: 16, display: 'flex', gap: 8 }}>
        <button onClick={handleGenerate} disabled={selected.length === 0}>Generate</button>
        <button onClick={onClose}>Cancel</button>
      </div>
    </Modal>
  );
}