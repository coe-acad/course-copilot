import React, { useRef } from "react";
import AssetSubCard from "./AssetSubCard";
import { FaChevronLeft, FaChevronRight, FaPlus } from 'react-icons/fa';

export default function SectionCard({ title, description, buttonLabel, style, onButtonClick, assets = [], courseId, onDeleteAsset, onResourceAdded, existingResources = [] }) {
  const scrollContainerRef = useRef(null);
  const scrollLeft = () => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollBy({ left: -300, behavior: 'smooth' });
    }
  };

  const scrollRight = () => {
    if (scrollContainerRef.current) {
      scrollContainerRef.current.scrollBy({ left: 300, behavior: 'smooth' });
    }
  };

  const subtitle = description;

  return (
    <div style={{ background: "#fff", borderRadius: 14, padding: "20px 26px", border: "1px solid #e8ecf2", boxShadow: "0 1px 3px rgba(15, 23, 42, 0.06)", width: "100%", boxSizing: "border-box", display: "flex", flexDirection: "column", ...style }}>
      <div style={{ display: "flex", alignItems: "center", gap: 14 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <h2 style={{ margin: 0, fontSize: 19, fontWeight: 700, color: "#111827" }}>{title}</h2>
            {assets.length > 0 && (
              <span style={{ fontSize: 12, fontWeight: 600, color: "#2563eb", background: "#eff4ff", borderRadius: 999, padding: "2px 8px" }}>{assets.length}</span>
            )}
          </div>
          {subtitle && <div style={{ fontSize: 14, color: "#6b7280", marginTop: 2 }}>{subtitle}</div>}
        </div>
        {buttonLabel && assets.length > 0 && (
          <button className="cc-section-btn" style={btnStyle} onClick={onButtonClick}><FaPlus style={{ fontSize: 11 }} />{buttonLabel}</button>
        )}
      </div>

      {/* Assets Sub-cards with Navigation */}
      {assets && assets.length > 0 && (
        <div style={{ 
          marginTop: 16,
          marginBottom: 2,
          width: "100%", 
          overflow: "visible", // allow arrows to show outside
          position: "relative"
        }}>
          {/* Left Arrow */}
          <button 
            onClick={scrollLeft}
            style={{
              position: "absolute",
              left: -18,
              top: "50%",
              transform: "translateY(-50%)",
              width: 40,
              height: 40,
              borderRadius: "50%",
              background: "#fff",
              border: "none",
              color: "#2563eb",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
              boxShadow: "0 2px 8px rgba(0,0,0,0.10)",
              transition: "background 0.2s, color 0.2s",
              zIndex: 10
            }}
            onMouseOver={e => { e.currentTarget.style.background = '#f0f4ff'; e.currentTarget.style.color = '#174ea6'; }}
            onMouseOut={e => { e.currentTarget.style.background = '#fff'; e.currentTarget.style.color = '#2563eb'; }}
          >
            <FaChevronLeft />
          </button>

          {/* Right Arrow */}
          <button 
            onClick={scrollRight}
            style={{
              position: "absolute",
              right: -18,
              top: "50%",
              transform: "translateY(-50%)",
              width: 40,
              height: 40,
              borderRadius: "50%",
              background: "#fff",
              border: "none",
              color: "#2563eb",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 20,
              boxShadow: "0 2px 8px rgba(0,0,0,0.10)",
              transition: "background 0.2s, color 0.2s",
              zIndex: 10
            }}
            onMouseOver={e => { e.currentTarget.style.background = '#f0f4ff'; e.currentTarget.style.color = '#174ea6'; }}
            onMouseOut={e => { e.currentTarget.style.background = '#fff'; e.currentTarget.style.color = '#2563eb'; }}
          >
            <FaChevronRight />
          </button>

          <div 
            ref={scrollContainerRef}
            style={{ 
              display: "flex", 
              gap: 12, 
              overflowX: "auto",
              paddingBottom: 6,
              scrollbarWidth: "none",
              msOverflowStyle: "none",
              paddingLeft: 40,
              paddingRight: 40
            }}
          >
            {assets.map((asset, index) => (
              <div key={index} style={{ flexShrink: 0 }}>
                <AssetSubCard
                  label={asset.type || "Asset"}
                  name={asset.name}
                  timestamp={asset.timestamp}
                  updatedBy={asset.updatedBy}
                  createdByUserId={asset.createdByUserId}
                  courseId={courseId}
                  onDelete={onDeleteAsset}
                  onResourceAdded={onResourceAdded}
                  existingResources={existingResources}
                />
              </div>
            ))}
          </div>
        </div>
      )}
      
      {buttonLabel && assets.length === 0 && (
        <div style={{ marginTop: 20, padding: "28px 16px", border: "1px dashed #d6dde8", borderRadius: 10, background: "#fafbfd", display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
          <span style={{ fontSize: 14, color: "#94a3b8" }}>Nothing here yet</span>
          <button className="cc-section-btn" style={btnStyle} onClick={onButtonClick}><FaPlus style={{ fontSize: 11 }} />{buttonLabel}</button>
        </div>
      )}
    </div>
  );
}

const btnStyle = {
  display: "inline-flex",
  alignItems: "center",
  gap: 8,
  padding: "8px 18px",
  borderRadius: 8,
  border: "1px solid #d0d7e2",
  background: "#fff",
  color: "#1f2937",
  fontWeight: 500,
  fontSize: 14,
  cursor: "pointer",
  flexShrink: 0,
  boxShadow: "0 1px 2px rgba(15, 23, 42, 0.05)",
  transition: "background 0.15s, border-color 0.15s, color 0.15s",
};
