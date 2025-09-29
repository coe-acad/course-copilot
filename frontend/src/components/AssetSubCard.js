import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { FiEye, FiTrash2 } from "react-icons/fi";
import { assetService } from "../services/asset";
import AssetViewModal from "./AssetViewModal";

export default function AssetSubCard({ 
  label, 
  name, 
  updatedBy = "", 
  timestamp,
  courseId,
  onView,
  onDownload,
  onDelete
}) {
  const navigate = useNavigate();
  const [isLoading, setIsLoading] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);
  const [showViewModal, setShowViewModal] = useState(false);
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [assetData, setAssetData] = useState(null);

  const handleView = async () => {
    if (!courseId || !name) return;
    
    setIsLoading(true);
    try {
      const asset = await assetService.viewAsset(courseId, name);
      // If this is an evaluation reference asset, open the live Evaluation UI by ID
      if (asset?.asset_category === 'evaluation' && asset?.asset_type === 'evaluation' && asset?.asset_content) {
        navigate(`/evaluation?evaluation_id=${encodeURIComponent(asset.asset_content)}`);
        return;
      }
      setAssetData(asset);
      setShowViewModal(true);
      if (onView) {
        onView(asset);
      }
    } catch (error) {
      console.error('Error viewing asset:', error);
      alert('Failed to view asset. Please try again.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteClick = () => {
    setShowDeleteConfirm(true);
  };

  const handleDeleteConfirm = async () => {
    if (!courseId || !name) return;
    
    setIsDeleting(true);
    try {
      await assetService.deleteAsset(courseId, name);
      setShowDeleteConfirm(false);
      if (onDelete) {
        onDelete(name);
      }
      // No alert needed - the UI will update instantly via onDelete callback
    } catch (error) {
      console.error('Error deleting asset:', error);
      alert('Failed to delete asset. Please try again.');
    } finally {
      setIsDeleting(false);
    }
  };

  const handleDeleteCancel = () => {
    setShowDeleteConfirm(false);
  };

  return (
    <>
      <div
        style={{
          minWidth: 220,
          background: "#fff",
          border: "1px solid #e5e7eb",
          borderRadius: 14,
          boxShadow: "0 2px 8px #0001",
          padding: "18px 20px",
          display: "flex",
          flexDirection: "column",
          alignItems: "flex-start",
          position: "relative",
          marginRight: 12,
        }}
      >
        {/* Action buttons - top right */}
        <div
          style={{
            position: "absolute",
            top: 12,
            right: 12,
            display: "flex",
            gap: 6,
          }}
        >
          <button
            onClick={handleView}
            disabled={isLoading}
            style={{
              background: "transparent",
              border: "none",
              color: "#666",
              cursor: isLoading ? "not-allowed" : "pointer",
              padding: "4px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.2s ease",
              opacity: isLoading ? 0.5 : 1,
            }}
            onMouseEnter={(e) => {
              if (!isLoading) {
                e.currentTarget.style.background = "#f3f4f6";
                e.currentTarget.style.color = "#2563eb";
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "#666";
            }}
            title="View asset"
          >
            <FiEye size={16} />
          </button>
          <button
            onClick={handleDeleteClick}
            disabled={isDeleting}
            style={{
              background: "transparent",
              border: "none",
              color: "#666",
              cursor: isDeleting ? "not-allowed" : "pointer",
              padding: "4px",
              borderRadius: "4px",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              transition: "all 0.2s ease",
              opacity: isDeleting ? 0.5 : 1,
            }}
            onMouseEnter={(e) => {
              if (!isDeleting) {
                e.currentTarget.style.background = "#fef2f2";
                e.currentTarget.style.color = "#dc2626";
              }
            }}
            onMouseLeave={(e) => {
              e.currentTarget.style.background = "transparent";
              e.currentTarget.style.color = "#666";
            }}
            title="Delete asset"
          >
            <FiTrash2 size={16} />
          </button>
        </div>

        {/* Pill label */}
        <div
          style={{
            background: "#f3f4f6",
            color: "#444",
            fontWeight: 600,
            fontSize: 13,
            borderRadius: 16,
            padding: "2px 12px",
            marginBottom: 10,
            display: "inline-block",
          }}
        >
          {label}
        </div>
        {/* Asset name */}
        <div
          style={{
            fontWeight: 700,
            fontSize: 18,
            marginBottom: 8,
            paddingRight: 80, // Increased padding for two buttons
          }}
        >
          {name}
        </div>
        {/* Last updated info */}
        <div
          style={{
            fontSize: 13,
            color: "#888",
            width: "100%",
          }}
        >
          <div style={{ 
            textAlign: "right",
            fontWeight: 500,
            color: "#666",
            marginBottom: 2
          }}>
            Last updated by {updatedBy}
          </div>
          <div style={{ 
            textAlign: "right",
            fontSize: 12,
            color: "#999"
          }}>
            {timestamp
              ? new Date(timestamp).toLocaleString("en-US", {
                  month: "short",
                  day: "numeric",
                  hour: "numeric",
                  minute: "2-digit",
                })
              : ""}
          </div>
        </div>
      </div>

      {/* Asset View Modal */}
      <AssetViewModal
        open={showViewModal}
        onClose={() => setShowViewModal(false)}
        assetData={assetData}
        courseId={courseId}
      />

      {/* Delete Confirmation Modal */}
      {showDeleteConfirm && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            backgroundColor: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000,
          }}
        >
          <div
            style={{
              background: "white",
              borderRadius: "12px",
              padding: "24px",
              maxWidth: "400px",
              width: "90%",
              boxShadow: "0 10px 25px rgba(0, 0, 0, 0.2)",
            }}
          >
            <h3
              style={{
                margin: "0 0 16px 0",
                fontSize: "18px",
                fontWeight: "600",
                color: "#1f2937",
              }}
            >
              Delete Asset
            </h3>
            <p
              style={{
                margin: "0 0 24px 0",
                color: "#6b7280",
                lineHeight: "1.5",
              }}
            >
              Are you sure you want to delete "<strong>{name}</strong>"? This action cannot be undone.
            </p>
            <div
              style={{
                display: "flex",
                gap: "12px",
                justifyContent: "flex-end",
              }}
            >
              <button
                onClick={handleDeleteCancel}
                disabled={isDeleting}
                style={{
                  background: "transparent",
                  border: "1px solid #d1d5db",
                  color: "#374151",
                  padding: "8px 16px",
                  borderRadius: "6px",
                  cursor: "pointer",
                  fontSize: "14px",
                  fontWeight: "500",
                  transition: "all 0.2s ease",
                }}
                onMouseEnter={(e) => {
                  if (!isDeleting) {
                    e.currentTarget.style.borderColor = "#9ca3af";
                  }
                }}
                onMouseLeave={(e) => {
                  e.currentTarget.style.borderColor = "#d1d5db";
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleDeleteConfirm}
                disabled={isDeleting}
                style={{
                  background: isDeleting ? "#fca5a5" : "#dc2626",
                  border: "none",
                  color: "white",
                  padding: "8px 16px",
                  borderRadius: "6px",
                  cursor: isDeleting ? "not-allowed" : "pointer",
                  fontSize: "14px",
                  fontWeight: "500",
                  transition: "all 0.2s ease",
                }}
                onMouseEnter={(e) => {
                  if (!isDeleting) {
                    e.currentTarget.style.background = "#b91c1c";
                  }
                }}
                onMouseLeave={(e) => {
                  if (!isDeleting) {
                    e.currentTarget.style.background = "#dc2626";
                  }
                }}
              >
                {isDeleting ? "Deleting..." : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}