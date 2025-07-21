import React, { useState } from "react";
import { ModalBase } from "./Modal";

const settingsModalStyle = {
  minWidth: 340,
  maxWidth: 420,
  width: "100%",
  minHeight: 320,
  maxHeight: 520,
  height: "auto",
  padding: "20px 16px 24px 16px",
  borderRadius: 14,
  display: "flex",
  flexDirection: "column",
  justifyContent: "center",
};

const courseLevels = ["Year 1", "Year 2", "Year 3", "Year 4"];
const studyAreas = [
  "AI & Decentralised Technologies",
  "Life Sciences",
  "Energy Sciences",
  "eMobility",
  "Climate Change",
  "Connected Intelligence"
];
const pedagogicalComponents = [
  "Theory",
  "Project",
  "Research",
  "Laboratory Experiments",
  "Unplugged Activities",
  "Programming Activities"
];

export default function SettingsModal({ open, onClose, onSave }) {
  const [selectedLevels, setSelectedLevels] = useState([]);
  const [selectedAreas, setSelectedAreas] = useState([]);
  const [selectedPedagogical, setSelectedPedagogical] = useState([]);
  const [useReferenceOnly, setUseReferenceOnly] = useState(false);
  const [askClarifying, setAskClarifying] = useState(false);

  const toggle = (arr, setArr, value) => {
    setArr(arr.includes(value) ? arr.filter(v => v !== value) : [...arr, value]);
  };

  const handleSave = () => {
    // backend integration: save settings to backend
    onSave && onSave({
      levels: selectedLevels,
      areas: selectedAreas,
      pedagogical: selectedPedagogical,
      useReferenceOnly,
      askClarifying
    });
    onClose();
  };

  return (
    <ModalBase open={open} onClose={onClose} modalStyle={settingsModalStyle}>
      <div style={{ fontWeight: 700, fontSize: 18, marginBottom: 6, display: "flex", alignItems: "center", gap: 8 }}>
        <span style={{ fontSize: 20 }}>🔧</span> Settings
      </div>
      <div style={{ fontWeight: 500, fontSize: 13, marginBottom: 12 }}>Course level <span style={{ fontWeight: 400, fontSize: 11 }}>(select all that are applicable)</span></div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        {courseLevels.map(level => (
          <button
            key={level}
            onClick={() => toggle(selectedLevels, setSelectedLevels, level)}
            style={{
              background: selectedLevels.includes(level) ? "#444" : "#f5f5f5",
              color: selectedLevels.includes(level) ? "#fff" : "#222",
              border: "none",
              borderRadius: 7,
              padding: "7px 12px",
              fontWeight: 500,
              fontSize: 13,
              cursor: "pointer"
            }}
          >
            {level}
          </button>
        ))}
      </div>
      <div style={{ fontWeight: 500, fontSize: 13, marginBottom: 6 }}>Study area</div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        {studyAreas.map(area => (
          <button
            key={area}
            onClick={() => toggle(selectedAreas, setSelectedAreas, area)}
            style={{
              background: selectedAreas.includes(area) ? "#444" : "#f5f5f5",
              color: selectedAreas.includes(area) ? "#fff" : "#222",
              border: "none",
              borderRadius: 7,
              padding: "7px 12px",
              fontWeight: 500,
              fontSize: 13,
              cursor: "pointer"
            }}
          >
            {area}
          </button>
        ))}
      </div>
      <div style={{ fontWeight: 500, fontSize: 13, marginBottom: 6 }}>Pedagogical Components <span style={{ fontWeight: 400, fontSize: 11 }}>(select all that are applicable)</span></div>
      <div style={{ display: "flex", gap: 8, marginBottom: 12, flexWrap: "wrap" }}>
        {pedagogicalComponents.map(pc => (
          <button
            key={pc}
            onClick={() => toggle(selectedPedagogical, setSelectedPedagogical, pc)}
            style={{
              background: selectedPedagogical.includes(pc) ? "#444" : "#f5f5f5",
              color: selectedPedagogical.includes(pc) ? "#fff" : "#222",
              border: "none",
              borderRadius: 7,
              padding: "7px 12px",
              fontWeight: 500,
              fontSize: 13,
              cursor: "pointer"
            }}
          >
            {pc}
          </button>
        ))}
      </div>
      <div style={{ marginBottom: 12 }}>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 500 }}>
          <span>Use reference material only</span>
          <input type="checkbox" checked={useReferenceOnly} onChange={e => setUseReferenceOnly(e.target.checked)} style={{ width: 18, height: 18 }} />
        </label>
        <div style={{ color: "#888", fontSize: 11, marginLeft: 2, marginTop: 2, marginBottom: 8 }}>
          <span style={{ fontSize: 13, marginRight: 4 }}>ℹ️</span> Limits AI-generated responses to the provided course materials and references.
        </div>
        <label style={{ display: "flex", alignItems: "center", gap: 8, fontSize: 13, fontWeight: 500 }}>
          <span>Ask clarifying questions</span>
          <input type="checkbox" checked={askClarifying} onChange={e => setAskClarifying(e.target.checked)} style={{ width: 18, height: 18 }} />
        </label>
        <div style={{ color: "#888", fontSize: 11, marginLeft: 2, marginTop: 2 }}>
          <span style={{ fontSize: 13, marginRight: 4 }}>ℹ️</span> Allows AI to ask targeted questions and gather necessary context before generating content.
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "flex-end", gap: 10, marginTop: 8 }}>
        <button onClick={onClose} style={{ padding: "7px 16px", borderRadius: 7, border: "none", background: "#fff", color: "#222", fontWeight: 500, fontSize: 14, cursor: "pointer", boxShadow: "0 1px 4px #0001" }}>Close</button>
        <button onClick={handleSave} style={{ padding: "7px 16px", borderRadius: 7, border: "none", background: "#222", color: "#fff", fontWeight: 600, fontSize: 14, cursor: "pointer", boxShadow: "0 1px 4px #0002" }}>Save Changes</button>
      </div>
    </ModalBase>
  );
} 