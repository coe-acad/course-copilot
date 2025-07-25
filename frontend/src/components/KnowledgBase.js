import React from "react";

export default function KnowledgeBase({
  resources = [],
  resourceLoading = false,
  resourceError = "",
  onAddResource,
  onSelectAll,
  onResourceCheck,
  fileInputRef,
  onFileChange,
  getFileIcon
}) {
  return (
    <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px #0001", padding: 18, maxHeight: '80vh', overflowY: 'auto' }}>
      <div style={{ fontWeight: 600, fontSize: 16, marginBottom: 4 }}>Knowledge base</div>
      <div style={{ color: "#888", fontSize: 13, marginBottom: 10 }}>Guides AI for content generation.</div>
      <input
        type="file"
        ref={fileInputRef}
        style={{ display: "none" }}
        multiple
        onChange={onFileChange}
      />
      <button
        style={{ width: "100%", marginBottom: 12, padding: "8px 0", borderRadius: 6, border: "1px solid #bbb", background: "#fff", fontWeight: 500, fontSize: 15, cursor: "pointer" }}
        onClick={onAddResource}
      >
        Add Resources
      </button>
      <div style={{ marginBottom: 8 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontWeight: 500, fontSize: 14 }}>
          <input
            type="checkbox"
            checked={resources.length > 0 && resources.every(r => r.status === "checked_in")}
            onChange={e => onSelectAll(e.target.checked)}
          /> Select All References
        </label>
      </div>
      <ul style={{ listStyle: "none", padding: 0, margin: 0 }}>
        {resourceLoading ? (
          <li>Loading resources...</li>
        ) : resourceError ? (
          <li style={{ color: 'red' }}>{resourceError}</li>
        ) : resources.length === 0 ? (
          <li style={{ color: '#888' }}>No resources uploaded yet.</li>
        ) : (
          resources.map((res, i) => {
            const id = res.fileId || res.id || res.fileName;
            return (
              <li key={id} style={{ display: "flex", alignItems: "center", justifyContent: "space-between", padding: "7px 0", borderBottom: i < resources.length - 1 ? "1px solid #f0f0f0" : "none" }}>
                <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 15, flex: 1 }}>
                  <input
                    type="checkbox"
                    checked={res.status === "checked_in"}
                    onChange={e => onResourceCheck(id, e.target.checked)}
                    disabled={resourceLoading}
                  />
                  <span>{getFileIcon ? getFileIcon(res) : "📄"}</span>
                  <span style={{ flex: 1 }}>{res.fileName || res.title}</span>
                </label>
                {res.url && (
                  <a href={res.url} target="_blank" rel="noopener noreferrer" style={{ color: '#2563eb', fontSize: 14, marginLeft: 8 }}>Download</a>
                )}
              </li>
            );
          })
        )}
      </ul>
    </div>
  );
}