import React, { useEffect, useMemo, useState } from "react";
import Modal from "./Modal";
import { assetService } from "../services/asset";

export default function ExportAssetsModal({
  open,
  onClose,
  assets: assetsProp,
  onExportSelected
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [assets, setAssets] = useState([]);
  const [selected, setSelected] = useState({});
  const [search, setSearch] = useState("");

  useEffect(() => {
    if (!open) return;
    setError("");
    setSelected({});
    const load = async () => {
      try {
        if (Array.isArray(assetsProp) && assetsProp.length) {
          // Ensure each asset has a stable unique id for selection
          const list = assetsProp.map((a, idx) => ({
            ...a,
            id: a.id || `${a.category || ""}|${a.type || ""}|${a.name || ""}|${a.updatedAt || idx}`
          }));
          setAssets(list);
          return;
        }
        setLoading(true);
        const courseId = localStorage.getItem("currentCourseId");
        if (!courseId) {
          setAssets([]);
          return;
        }
        const data = await assetService.getAssets(courseId);
        const list = (data?.assets || []).map((a, idx) => ({
          id: `${a.asset_category || ""}|${a.asset_type || ""}|${a.asset_name || ""}|${a.asset_last_updated_at || idx}`,
          name: a.asset_name,
          type: a.asset_type,
          category: a.asset_category,
          updatedAt: a.asset_last_updated_at,
          updatedBy: a.asset_last_updated_by
        }));
        setAssets(list);
      } catch (e) {
        setError(e?.message || "Failed to load assets");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [open, assetsProp]);

  const filteredAssets = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return assets;
    return assets.filter(a =>
      a.name.toLowerCase().includes(q) ||
      (a.type || "").toLowerCase().includes(q) ||
      (a.category || "").toLowerCase().includes(q)
    );
  }, [assets, search]);

  const grouped = useMemo(() => {
    const groups = {};
    filteredAssets.forEach(a => {
      const key = (a.category || "Other");
      if (!groups[key]) groups[key] = [];
      groups[key].push(a);
    });
    return groups;
  }, [filteredAssets]);

  const totalCount = filteredAssets.length;
  const selectedIds = Object.keys(selected).filter(k => selected[k]);
  const selectedCount = selectedIds.length;
  const allChecked = totalCount > 0 && selectedCount === totalCount;
  const someChecked = selectedCount > 0 && selectedCount < totalCount;

  const toggleAll = () => {
    if (allChecked) {
      setSelected({});
    } else {
      const next = {};
      filteredAssets.forEach(a => { next[a.id] = true; });
      setSelected(next);
    }
  };

  const toggleOne = (id) => {
    setSelected(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleExport = () => {
    const chosen = assets.filter(a => selected[a.id]);
    if (onExportSelected) onExportSelected(chosen);
    onClose?.();
  };

  if (!open) return null;

  return (
    <Modal open={open} onClose={onClose}>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
          <div style={{ fontWeight: 700, fontSize: 22 }}>Export Assets</div>
          <div style={{ color: "#6b7280", fontSize: 14 }}>
            {selectedCount} selected{totalCount ? ` / ${totalCount}` : ""}
          </div>
        </div>

        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search by name, type, or category"
            style={{ flex: 1, padding: "10px 12px", border: "1px solid #d1d5db", borderRadius: 8 }}
          />
          <label style={{ display: "flex", alignItems: "center", gap: 8, userSelect: "none", cursor: "pointer" }}>
            <input
              type="checkbox"
              checked={allChecked}
              ref={el => { if (el) el.indeterminate = someChecked; }}
              onChange={toggleAll}
            />
            <span style={{ fontWeight: 600 }}>Select all</span>
          </label>
        </div>

        {error && (
          <div style={{ color: "#b91c1c", background: "#fee2e2", padding: 10, borderRadius: 8 }}>{error}</div>
        )}

        <div style={{
          maxHeight: "50vh",
          overflowY: "auto",
          border: "1px solid #e5e7eb",
          borderRadius: 10,
          background: "#fafbfc",
          padding: 8
        }}>
          {loading ? (
            <div style={{ padding: 16 }}>Loading assets…</div>
          ) : (
            Object.keys(grouped).sort().map(group => (
              <div key={group} style={{ marginBottom: 10 }}>
                <div style={{
                  position: "sticky",
                  top: 0,
                  background: "#f5f8ff",
                  padding: "8px 10px",
                  borderRadius: 8,
                  fontWeight: 700,
                  color: "#2563eb",
                  border: "1px solid #e5e7eb"
                }}>{group.charAt(0).toUpperCase() + group.slice(1)}</div>
                <div style={{ display: "flex", flexDirection: "column", marginTop: 6 }}>
                  {grouped[group].map(item => (
                    <label key={item.id} style={{
                      display: "grid",
                      gridTemplateColumns: "24px 1fr auto",
                      alignItems: "center",
                      gap: 10,
                      padding: "8px 10px",
                      borderBottom: "1px solid #eef2f7",
                      background: selected[item.id] ? "#eef6ff" : "transparent",
                      cursor: "pointer",
                      borderRadius: 6
                    }}>
                      <input type="checkbox" checked={!!selected[item.id]} onChange={() => toggleOne(item.id)} />
                      <div style={{ display: "flex", flexDirection: "column" }}>
                        <span style={{ fontWeight: 600 }}>{item.name}</span>
                        <span style={{ fontSize: 12, color: "#6b7280" }}>{item.type}</span>
                      </div>
                      <div style={{ fontSize: 12, color: "#6b7280" }}>
                        {item.updatedAt ? new Date(item.updatedAt).toLocaleString() : ""}
                      </div>
                    </label>
                  ))}
                </div>
              </div>
            ))
          )}
          {!loading && totalCount === 0 && (
            <div style={{ padding: 16, color: "#6b7280" }}>No assets found.</div>
          )}
        </div>

        <div style={{ display: "flex", justifyContent: "flex-end", gap: 12 }}>
          <button onClick={onClose} style={{ padding: "10px 16px", borderRadius: 8, border: "1px solid #d1d5db", background: "#fff" }}>Cancel</button>
          <button
            onClick={handleExport}
            disabled={selectedCount === 0}
            style={{
              padding: "10px 16px",
              borderRadius: 8,
              border: "none",
              background: selectedCount === 0 ? "#94a3b8" : "#2563eb",
              color: "#fff",
              fontWeight: 600,
              cursor: selectedCount === 0 ? "not-allowed" : "pointer"
            }}
          >
            Export {selectedCount > 0 ? `(${selectedCount})` : ""}
          </button>
        </div>
      </div>
    </Modal>
  );
}


