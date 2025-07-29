import React, { useState, useRef } from "react";
import AssetSubCard from "./AssetSubCard";

export default function SectionCard({ title, description, buttonLabel, style, onButtonClick, assets = [] }) {
  const [scrollPosition, setScrollPosition] = useState(0);
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

  return (
    <div style={{ background: "#fff", borderRadius: 12, boxShadow: "0 1px 4px #0001", padding: "32px 36px", minHeight: 140, display: "flex", flexDirection: "column", justifyContent: "center", ...style }}>
      <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
        <h2 style={{ margin: 0, fontSize: 24, fontWeight: 600, flex: 1 }}>{title}</h2>
        {buttonLabel && assets.length > 0 && (
          <button style={btnStyle} onClick={onButtonClick}>{buttonLabel}</button>
        )}
      </div>
      {description && <span style={{ fontSize: 16, color: "#222", marginTop: 12, marginBottom: 24 }}>{description}</span>}
      
      {/* Assets Sub-cards with Navigation */}
      {assets && assets.length > 0 && (
        <div style={{ 
          marginTop: 20, 
          marginBottom: 24, 
          width: "100%", 
          overflow: "hidden",
          position: "relative"
        }}>
          {/* Left Arrow */}
          <button 
            onClick={scrollLeft}
            style={{
              position: "absolute",
              left: -10,
              top: "50%",
              transform: "translateY(-50%)",
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: "#3b82f6",
              border: "none",
              color: "white",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 16,
              fontWeight: "bold",
              zIndex: 10,
              boxShadow: "0 2px 8px rgba(0,0,0,0.1)"
            }}
          >
            ‹
          </button>

          {/* Right Arrow */}
          <button 
            onClick={scrollRight}
            style={{
              position: "absolute",
              right: -10,
              top: "50%",
              transform: "translateY(-50%)",
              width: 32,
              height: 32,
              borderRadius: "50%",
              background: "#3b82f6",
              border: "none",
              color: "white",
              cursor: "pointer",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 16,
              fontWeight: "bold",
              zIndex: 10,
              boxShadow: "0 2px 8px rgba(0,0,0,0.1)"
            }}
          >
            ›
          </button>

          <div 
            ref={scrollContainerRef}
            style={{ 
              display: "flex", 
              gap: 12, 
              overflowX: "auto",
              paddingBottom: 8,
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
                />
              </div>
            ))}
          </div>
        </div>
      )}
      
      {buttonLabel && assets.length === 0 && (
        <div style={{ display: "flex", justifyContent: "center", marginTop: description ? 0 : 24 }}>
          <button style={btnStyle} onClick={onButtonClick}>{buttonLabel}</button>
        </div>
      )}
    </div>
  );
}

const btnStyle = {
  padding: "8px 22px",
  borderRadius: 6,
  border: "1px solid #bbb",
  background: "#fff",
  fontWeight: 500,
  fontSize: 15,
  cursor: "pointer",
  marginLeft: 0,
  boxShadow: "0 1px 2px #0001",
  transition: "background 0.2s",
}; 