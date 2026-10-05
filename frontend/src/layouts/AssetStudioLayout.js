import React from "react";
import SettingsModal from "../components/SettingsModal";
import StudioHeader from "../components/header/StudioHeader";
import { useNavigate } from "react-router-dom";
import { logout } from "../services/auth";

// Both panels fill the space left by the fixed header and scroll internally, so the
// page itself never scrolls.
const PANEL_STYLE = {
  height: "100%",
  minHeight: 0,
  borderRadius: 12,
  padding: 20,
  // Without this the 20px padding is added to the 100% height and the panel
  // overflows the viewport, clipping the composer at the bottom.
  boxSizing: "border-box"
};

export default function AssetStudioLayout({ title = "AI Studio", children, rightPanel }) {
  const [showSettingsModal, setShowSettingsModal] = React.useState(false);
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  return (
    <div style={{ height: "100vh", overflow: "hidden", background: "#e6f0fc", display: "flex", flexDirection: "column" }}>
      {/* Header (fixed: never scrolls) */}
      <div style={{ flexShrink: 0 }}>
        <StudioHeader
          title={title}
          onSettings={() => setShowSettingsModal(true)}
          onLogout={handleLogout}
        />
      </div>

      {/* Content Area */}
      <div style={{
        display: "flex",
        justifyContent: "center",
        alignItems: "stretch",
        gap: 20,
        padding: "20px 28px",
        flex: 1,
        minHeight: 0,
        overflow: "hidden",
        // Keep line lengths readable on very wide screens
        width: "100%",
        maxWidth: 1600,
        margin: "0 auto",
        boxSizing: "border-box"
      }}>
        {/* Left Main Panel */}
        <div style={{
          ...PANEL_STYLE,
          flex: 2,
          minWidth: 0,
          background: "#fff",
          boxShadow: "0 2px 10px rgba(0,0,0,0.08)",
          // Column flow so the chat transcript scrolls inside the panel
          display: "flex",
          flexDirection: "column",
          overflow: "hidden"
        }}>
          {children}
        </div>

        {/* Right Knowledge Base (the list inside it does the scrolling) */}
        <div style={{
          ...PANEL_STYLE,
          flex: "0 1 400px",
          minWidth: 300,
          background: "#fefefe",
          boxShadow: "0 1px 6px rgba(0,0,0,0.06)",
          overflow: "hidden",
          position: "relative"
        }}>
          {rightPanel}
        </div>
      </div>

      {/* Settings Modal */}
      <SettingsModal open={showSettingsModal} onClose={() => setShowSettingsModal(false)} />
    </div>
  );
}
