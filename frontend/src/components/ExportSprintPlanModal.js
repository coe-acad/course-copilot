import React, { useState, useEffect } from "react";
import Modal from "./Modal";
import { assetService } from "../services/asset";
import { getAllResources, viewResource } from "../services/resources";
import { getCourse } from "../services/course";

export default function ExportSprintPlanModal({
  open,
  onClose,
  onSprintPlanCreated,
}) {
  const [loading, setLoading] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [generationStatus, setGenerationStatus] = useState(""); // Track current generation phase
  const [error, setError] = useState("");
  const [allAssets, setAllAssets] = useState([]);
  const [courseDescription, setCourseDescription] = useState(null);
  const [courseDescriptionContent, setCourseDescriptionContent] = useState(null);
  const [selectedCO, setSelectedCO] = useState(null);
  const [selectedModules, setSelectedModules] = useState(null);
  const [selectedPOPSO, setSelectedPOPSO] = useState([]);

  useEffect(() => {
    if (!open) return;
    setError("");
    setGenerationStatus("");
    setSelectedCO(null);
    setSelectedModules(null);
    setSelectedPOPSO([]);
    setCourseDescription(null);
    setCourseDescriptionContent(null);

    const load = async () => {
      let courseDescriptionText = null;
      try {
        setLoading(true);
        const courseId = localStorage.getItem("currentCourseId");
        if (!courseId) {
          setAllAssets([]);
          return;
        }

        // Get all assets
        const assetData = await assetService.getAssets(courseId);
        const assetsList = (assetData?.assets || []).map((a, idx) => ({
          id: `${a.asset_category || ""}|${a.asset_type || ""}|${a.asset_name || ""}|${a.asset_last_updated_at || idx}`,
          name: a.asset_name,
          type: a.asset_type,
          category: a.asset_category,
          updatedAt: a.asset_last_updated_at,
          updatedBy: a.asset_last_updated_by,
          source: "asset",
        }));

        // Get knowledge base resources
        const resourcesData = await getAllResources(courseId);
        const resourcesList = (resourcesData.resources || []).map((r, idx) => ({
          id: `resource|${r.resourceName || r.fileName || idx}`,
          name: r.resourceName || r.fileName,
          fileName: r.resourceName || r.fileName,
          type: "resource",
          category: "resource",
          updatedAt: new Date().toISOString(),
          updatedBy: "System",
          source: "resource",
        }));

        // Find course description file (contains "Course_Description" in filename)
        const courseDescriptionResource = resourcesList.find(
          (r) => r.fileName && r.fileName.includes("Course_Description")
        );

        if (courseDescriptionResource) {
          try {
            const contentData = await viewResource(courseId, courseDescriptionResource.fileName);
            courseDescriptionText = contentData.content || contentData || "Course description not available";
            setCourseDescriptionContent(courseDescriptionText);
          } catch (resourceError) {
            console.warn("Could not load course description from resource:", resourceError);
            // Fallback to course API if resource content cannot be read
            try {
              const courseData = await getCourse(courseId);
              courseDescriptionText = courseData.description || "Course description not available";
              setCourseDescriptionContent(courseDescriptionText);
            } catch (courseError) {
              console.warn("Could not load course description from API:", courseError);
              courseDescriptionText = "Course description not available";
              setCourseDescriptionContent(courseDescriptionText);
            }
          }
        } else {
          try {
            const courseData = await getCourse(courseId);
            courseDescriptionText = courseData.description || "Course description not available";
            setCourseDescriptionContent(courseDescriptionText);
          } catch (courseError) {
            console.warn("Could not load course description from API:", courseError);
            courseDescriptionText = "Course description not available";
            setCourseDescriptionContent(courseDescriptionText);
          }
        }
        
        if (courseDescriptionResource) {
          setCourseDescription(courseDescriptionResource.fileName);
        } else if (courseDescriptionText && courseDescriptionText !== "Course description not available") {
          // When the course description exists in course metadata but no resource file yet,
          // still allow sprint plan generation by supplying a placeholder course description source.
          setCourseDescription("Course_Description");
        }

        const initialSelectedResources = [];
        if (courseDescriptionResource) {
          initialSelectedResources.push(courseDescriptionResource.fileName);
        }

        const firstKnowledgeBaseDoc = resourcesList.find(
          (r) => r.fileName && r.fileName !== courseDescriptionResource?.fileName
        );
        if (firstKnowledgeBaseDoc) {
          initialSelectedResources.push(firstKnowledgeBaseDoc.fileName);
        }

        if (initialSelectedResources.length > 0) {
          setSelectedPOPSO(initialSelectedResources);
        }

        setAllAssets([...assetsList, ...resourcesList]);
      } catch (e) {
        setError(e?.message || "Failed to load assets");
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [open]);

  const handleExport = async () => {
    try {
      setExporting(true);
      setError("");
      setGenerationStatus("");

      // Validate course description
      if (!courseDescription) {
        setError("Course description not found. Please ensure the course was created properly.");
        setExporting(false);
        return;
      }

      // Validate course description content
      if (!courseDescriptionContent || courseDescriptionContent === "Course description not available") {
        setError("Course description is not ready. Please wait until it loads fully before creating the sprint plan.");
        setExporting(false);
        return;
      }

      // Validate selections
      if (!selectedCO) {
        setError("Please select a Course Outcome document");
        setExporting(false);
        return;
      }

      if (!selectedModules) {
        setError("Please select a Modules document");
        setExporting(false);
        return;
      }

      // Calculate selected additional resources (PO-PSO)
      const selectedResourceNames = selectedPOPSO || [];
      const selectedAdditionalResources = selectedResourceNames.filter(
        (name) => name !== courseDescription
      );

      if (selectedAdditionalResources.length === 0) {
        setError("Please select a PO-PSO document");
        setExporting(false);
        return;
      }

      const selectedPoPsoFile = selectedAdditionalResources[0];
      const courseId = localStorage.getItem("currentCourseId");
      if (!courseId) {
        setError("Course ID not found");
        setExporting(false);
        return;
      }

      // Prepare file names in order: Course Description, CO, Modules, PO-PSO
      const fileNames = [courseDescription, selectedCO, selectedModules, selectedPoPsoFile];

      console.log("Generating sprint plan with selected documents:", {
        courseDescription,
        co: selectedCO,
        modules: selectedModules,
        poPso: selectedPoPsoFile,
      });

      // Call createAssetChat to trigger sprint-plan generation via the backend
      setGenerationStatus("Generating sprint plan...");
      const taskResponse = await assetService.createAssetChat(courseId, "sprint-plan", fileNames, courseDescriptionContent);
      const taskId = taskResponse?.task_id;

      if (!taskId) {
        setError("Failed to start sprint plan generation");
        setExporting(false);
        return;
      }

      // Poll for task completion
      let taskStatus = null;
      let taskMetadata = null;
      let maxAttempts = 600; // 10 minutes with 1 second intervals
      let attempt = 0;

      while (attempt < maxAttempts) {
        try {
          const statusResponse = await assetService.getTaskStatus(taskId);
          if (statusResponse.status === "completed") {
            taskStatus = statusResponse;
            taskMetadata = statusResponse.metadata;
            break;
          } else if (statusResponse.status === "failed") {
            setError(statusResponse.error || "Sprint plan generation failed");
            setExporting(false);
            return;
          }
          // Still processing, wait before next poll
          await new Promise(resolve => setTimeout(resolve, 1000));
          attempt++;
        } catch (pollError) {
          console.error("Error polling task status:", pollError);
          await new Promise(resolve => setTimeout(resolve, 1000));
          attempt++;
        }
      }

      if (!taskStatus || taskStatus.status !== "completed") {
        setError("Sprint plan generation timed out");
        setExporting(false);
        return;
      }

      const generatedText = taskStatus.result?.response;
      if (generatedText && typeof generatedText === "string") {
        setGenerationStatus("Saving sprint plan...");
        const finalSprintText = generatedText.trim();
        const timestamp = new Date().toISOString().split('T')[0]; // YYYY-MM-DD format
        const sprintPlanName = `Sprint Plan ${timestamp}`;

        // Extract created_at from task metadata (when the task was created)
        const createdAt = taskMetadata?.created_at;

        // Save the generated sprint plan as an asset with the task creation time
        await assetService.saveAsset(courseId, sprintPlanName, "sprint-plan", finalSprintText, createdAt);

        setGenerationStatus("Sprint plan created successfully!");
        // Trigger callback to refresh assets in parent component
        onSprintPlanCreated?.();

        setTimeout(() => {
          onClose?.();
        }, 1500);
      } else {
        setError("Failed to generate sprint plan content");
      }
    } catch (error) {
      console.error("Export error:", error);
      setError(error.message || "Failed to create sprint plan");
    } finally {
      setExporting(false);
    }
  };

  // Categorize assets
  const courseOutcomes = allAssets.filter((a) => a.type === "course-outcomes");
  const moduleAssets = allAssets.filter((a) => a.type === "modules");
  const poPoResources = allAssets.filter((a) => a.source === "resource");

  // Calculate selected resources and validation state
  const selectedResourceNames = selectedPOPSO || [];
  const hasSelectedAdditionalResource = selectedResourceNames.some(
    (name) => name !== courseDescription
  );
  const isComplete = courseDescription && selectedCO && selectedModules && hasSelectedAdditionalResource;
  const canGeneratePlan = isComplete && !exporting && !generationStatus;

  return (
    <Modal open={open} onClose={onClose}>
      <div
        style={{
          display: "flex",
          flexDirection: "column",
          gap: 20,
          position: "relative",
          width: "100%",
          boxSizing: "border-box",
          padding: 0,
        }}
      >
        {/* Header */}
        <div>
          <div style={{ fontWeight: 700, fontSize: 22, marginBottom: 8 }}>
            📋 Create Sprint Plan
          </div>
          <div style={{ fontSize: 14, color: "#666", marginBottom: 16 }}>
            Select one document from each category below to generate a comprehensive sprint planning document:
          </div>
        </div>

        {/* Course Description Preview */}
        {courseDescription && (
          <div
            style={{
              border: "1px solid #dbeafe",
              borderRadius: 14,
              padding: 18,
              background: "#eff6ff",
              width: "100%",
              boxSizing: "border-box",
            }}
          >
            <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 10, color: "#0369a1" }}>
              📄 Course Description
            </div>
            {courseDescriptionContent ? (
              <div style={{ fontSize: 13, color: "#0c4a6e", lineHeight: 1.6, whiteSpace: "pre-wrap", wordBreak: "break-word", overflowWrap: "anywhere" }}>
                {courseDescriptionContent}
              </div>
            ) : (
              <div style={{ fontSize: 13, color: "#0c4a6e" }}>
                Loading description...
              </div>
            )}
          </div>
        )}

        {loading ? (
          <div style={{ padding: 20, textAlign: "center", color: "#999" }}>
            Loading assets...
          </div>
        ) : (
          <>
            {/* Course Outcomes Section */}
            <div
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                padding: 16,
                background: "#fafbfc",
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12, color: "#333" }}>
                1️⃣ Course Outcome {selectedCO && <span style={{ color: "#16a34a" }}>✓</span>}
              </div>
              {courseOutcomes.length === 0 ? (
                <div style={{ fontSize: 13, color: "#999" }}>
                  No Course Outcome assets found. Please create one first.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {courseOutcomes.map((asset) => (
                    <label
                      key={asset.id}
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 12,
                        cursor: "pointer",
                        padding: "8px 12px",
                        borderRadius: 6,
                        background: selectedCO === asset.name ? "#e8f5e9" : "transparent",
                        wordBreak: "break-word",
                      }}
                    >
                      <input
                        type="radio"
                        name="courseOutcome"
                        checked={selectedCO === asset.name}
                        onChange={() => setSelectedCO(asset.name)}
                        style={{ width: 18, height: 18, cursor: "pointer", marginTop: 4 }}
                      />
                      <span style={{ fontSize: 13, fontWeight: 500, minWidth: 0, wordBreak: "break-word", overflowWrap: "anywhere", whiteSpace: "normal" }}>
                        {asset.name}
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* Modules Section */}
            <div
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                padding: 16,
                background: "#fafbfc",
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 12, color: "#333" }}>
                2️⃣ Modules {selectedModules && <span style={{ color: "#16a34a" }}>✓</span>}
              </div>
              {moduleAssets.length === 0 ? (
                <div style={{ fontSize: 13, color: "#999" }}>
                  No Modules assets found. Please create one first.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {moduleAssets.map((asset) => (
                    <label
                      key={asset.id}
                      style={{
                        display: "flex",
                        alignItems: "flex-start",
                        gap: 12,
                        cursor: "pointer",
                        padding: "8px 12px",
                        borderRadius: 6,
                        background: selectedModules === asset.name ? "#e8f5e9" : "transparent",
                        wordBreak: "break-word",
                      }}
                    >
                      <input
                        type="radio"
                        name="modules"
                        checked={selectedModules === asset.name}
                        onChange={() => setSelectedModules(asset.name)}
                        style={{ width: 18, height: 18, cursor: "pointer", marginTop: 4 }}
                      />
                      <span style={{ fontSize: 13, fontWeight: 500, minWidth: 0, wordBreak: "break-word", overflowWrap: "anywhere", whiteSpace: "normal" }}>
                        {asset.name}
                      </span>
                    </label>
                  ))}
                </div>
              )}
            </div>

            {/* PO-PSO Resources Section */}
            <div
              style={{
                border: "1px solid #e5e7eb",
                borderRadius: 8,
                padding: 16,
                background: "#fafbfc",
              }}
            >
              <div style={{ fontWeight: 600, fontSize: 14, marginBottom: 8, color: "#333" }}>
                3️⃣ PO-PSO Document {hasSelectedAdditionalResource && <span style={{ color: "#16a34a" }}>✓</span>}
              </div>
              <div style={{ fontSize: 13, color: "#555", marginBottom: 10 }}>
                The Course Description PDF is auto-selected when available. Choose one additional resource for PO-PSO mapping.
              </div>
              {poPoResources.length === 0 ? (
                <div style={{ fontSize: 13, color: "#999" }}>
                  No PO-PSO documents found in uploaded resources. Please upload one first.
                </div>
              ) : (
                <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                  {poPoResources.map((resource) => {
                    const isCourseDescriptionFile = resource.fileName === courseDescription;
                    const isSelected = selectedResourceNames.includes(resource.fileName);
                    const additionalSelectedCount = selectedResourceNames.filter(
                      (name) => name !== courseDescription
                    ).length;
                    const isDisabled = isCourseDescriptionFile;
                    return (
                      <label
                        key={resource.id}
                        style={{
                          display: "flex",
                          alignItems: "flex-start",
                          gap: 12,
                          cursor: isDisabled ? "default" : "pointer",
                          padding: "8px 12px",
                          borderRadius: 6,
                          background: isSelected ? "#e8f5e9" : "transparent",
                          wordBreak: "break-word",
                          opacity: isDisabled ? 0.75 : 1,
                        }}
                      >
                        <input
                          type="checkbox"
                          name="poPso"
                          checked={isSelected}
                          disabled={isDisabled}
                          onChange={() => {
                            if (isCourseDescriptionFile) return;
                            if (isSelected) {
                              setSelectedPOPSO((prev) => prev.filter((name) => name !== resource.fileName));
                            } else if (additionalSelectedCount < 1) {
                              setSelectedPOPSO((prev) => [...prev, resource.fileName]);
                            }
                          }}
                          style={{ width: 18, height: 18, cursor: isDisabled ? "not-allowed" : "pointer", marginTop: 4 }}
                        />
                        <span style={{ fontSize: 13, fontWeight: 500, minWidth: 0, wordBreak: "break-word", overflowWrap: "anywhere", whiteSpace: "normal" }}>
                          {resource.fileName}{isCourseDescriptionFile ? " (Course Description - auto-selected)" : ""}
                        </span>
                      </label>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Validation Message */}
            {!isComplete && (
              <div
                style={{
                  padding: "12px 16px",
                  background: "#fff3cd",
                  color: "#856404",
                  borderRadius: 6,
                  fontSize: 13,
                  border: "1px solid #ffc107",
                }}
              >
                ⚠️ {!courseDescription
                  ? "Course description document not found. Please add or upload a Course Description file."
                  : "Please select one item from each category"}
              </div>
            )}

            {/* Error Message */}
            {error && (
              <div
                style={{
                  padding: "12px 16px",
                  background: "#fee",
                  color: "#d32f2f",
                  borderRadius: 6,
                  fontSize: 13,
                  border: "1px solid #f5222d",
                }}
              >
                ❌ {error}
              </div>
            )}

            {/* Status Message */}
            {generationStatus && (
              <div
                style={{
                  padding: "12px 16px",
                  background: "#e3f2fd",
                  color: "#1976d2",
                  borderRadius: 6,
                  fontSize: 13,
                  border: "1px solid #90caf9",
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <span style={{
                  display: "inline-block",
                  width: 12,
                  height: 12,
                  borderRadius: "50%",
                  background: "#1976d2",
                  animation: "pulse 1.5s infinite"
                }}></span>
                ℹ️ {generationStatus}
              </div>
            )}

            {/* Actions */}
            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button
                onClick={onClose}
                disabled={exporting || !!generationStatus}
                style={{
                  padding: "10px 20px",
                  borderRadius: 6,
                  border: "1px solid #ddd",
                  background: "#fff",
                  cursor: exporting || generationStatus ? "not-allowed" : "pointer",
                  fontWeight: 500,
                  fontSize: 14,
                  opacity: exporting || generationStatus ? 0.6 : 1,
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleExport}
                disabled={!canGeneratePlan}
                style={{
                  padding: "10px 20px",
                  borderRadius: 6,
                  border: "none",
                  background: canGeneratePlan ? "#16a34a" : "#ccc",
                  color: "#fff",
                  cursor: canGeneratePlan ? "pointer" : "not-allowed",
                  fontWeight: 500,
                  fontSize: 14,
                }}
              >
                {exporting || generationStatus ? "Creating..." : "Create Sprint Plan"}
              </button>
            </div>

            <style>{`
              @keyframes pulse {
                0%, 100% { opacity: 1; }
                50% { opacity: 0.5; }
              }
            `}</style>
          </>
        )}
      </div>
    </Modal>
  );
}
