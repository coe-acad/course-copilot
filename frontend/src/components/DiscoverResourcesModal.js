import React, { useState } from "react";
import { FiX, FiSearch } from "react-icons/fi";
import Modal from "./Modal";
import { discoverResources } from "../services/resources";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function DiscoverResourcesModal({ open, onClose, courseId }) {
    const [query, setQuery] = useState("");
    const [resources, setResources] = useState([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    const handleDiscover = async () => {
        if (!query.trim()) {
            setError("Please enter a topic to search for resources");
            return;
        }

        setLoading(true);
        setError(null);
        setResources([]);

        try {
            const result = await discoverResources(courseId, query);
            setResources(result.resources || "");
        } catch (err) {
            console.error("Error discovering resources:", err);
            setError(err.message || "Failed to discover resources");
        } finally {
            setLoading(false);
        }
    };

    const handleKeyPress = (e) => {
        if (e.key === "Enter" && !loading) {
            handleDiscover();
        }
    };

    const handleClose = () => {
        setQuery("");
        setResources([]);
        setError(null);
        onClose();
    };

    return (
        <Modal open={open} onClose={handleClose}>
            <div
                style={{
                    position: "relative",
                    maxHeight: "90vh",
                    overflow: "hidden",
                    display: "flex",
                    flexDirection: "column",
                }}
            >
                {/* Header */}
                <div
                    style={{
                        marginBottom: "24px",
                        flexShrink: 0,
                    }}
                >
                    <h3
                        style={{
                            margin: 0,
                            fontSize: "18px",
                            fontWeight: 600,
                            color: "#1f2937",
                            marginBottom: "8px",
                        }}
                    >
                        Discover Resources
                    </h3>
                    <p
                        style={{
                            margin: 0,
                            fontSize: "14px",
                            color: "#6b7280",
                        }}
                    >
                        Search the web for high-quality educational resources
                    </p>
                </div>

                {/* Search Input */}
                <div style={{ marginBottom: "20px", flexShrink: 0 }}>
                    <div style={{ position: "relative" }}>
                        <input
                            type="text"
                            value={query}
                            onChange={(e) => setQuery(e.target.value)}
                            onKeyPress={handleKeyPress}
                            placeholder="Enter a topic (e.g., Machine Learning, Python Programming)"
                            style={{
                                width: "100%",
                                padding: "12px 110px 12px 12px",
                                fontSize: "14px",
                                border: "1.5px solid #e5e7eb",
                                borderRadius: "10px",
                                outline: "none",
                                background: "#fafbfc",
                                transition: "border 0.18s, background 0.18s",
                            }}
                            onFocus={(e) => {
                                e.currentTarget.style.border = "1.5px solid #2563eb";
                            }}
                            onBlur={(e) => {
                                e.currentTarget.style.border = "1.5px solid #e5e7eb";
                            }}
                        />
                        <button
                            onClick={handleDiscover}
                            disabled={loading || !query.trim()}
                            style={{
                                position: "absolute",
                                right: "8px",
                                top: "50%",
                                transform: "translateY(-50%)",
                                background: loading || !query.trim() ? "#e5e7eb" : "#2563eb",
                                border: "none",
                                borderRadius: "6px",
                                padding: "6px 12px",
                                cursor: loading || !query.trim() ? "not-allowed" : "pointer",
                                display: "flex",
                                alignItems: "center",
                                gap: "6px",
                                fontSize: "14px",
                                fontWeight: 500,
                                color: "white",
                                transition: "all 0.2s ease",
                                whiteSpace: "nowrap",
                            }}
                            onMouseEnter={(e) => {
                                if (!loading && query.trim()) {
                                    e.currentTarget.style.background = "#1d4ed8";
                                }
                            }}
                            onMouseLeave={(e) => {
                                if (!loading && query.trim()) {
                                    e.currentTarget.style.background = "#2563eb";
                                }
                            }}
                        >
                            <FiSearch size={16} />
                            {loading ? "Searching..." : "Search"}
                        </button>
                    </div>
                </div>

                {/* Error Message */}
                {error && (
                    <div
                        style={{
                            padding: "12px",
                            background: "#fef2f2",
                            border: "1px solid #fecaca",
                            borderRadius: "8px",
                            color: "#dc2626",
                            fontSize: "14px",
                            marginBottom: "16px",
                            flexShrink: 0,
                        }}
                    >
                        {error}
                    </div>
                )}

                {/* Loading State */}
                {loading && (
                    <div
                        style={{
                            display: "flex",
                            justifyContent: "center",
                            alignItems: "center",
                            padding: "40px",
                            color: "#6b7280",
                            flex: 1,
                        }}
                    >
                        <div
                            style={{
                                width: "24px",
                                height: "24px",
                                border: "3px solid #e5e7eb",
                                borderTop: "3px solid #2563eb",
                                borderRadius: "50%",
                                animation: "spin 1s linear infinite",
                                marginRight: "12px",
                            }}
                        />
                        <span style={{ fontSize: "14px" }}>Discovering resources...</span>
                    </div>
                )}

                {/* Resources List */}
                {!loading && resources && (
                    <div
                        style={{
                            flex: 1,
                            overflowY: "auto",
                            marginBottom: "16px",
                            maxHeight: "400px",
                        }}
                    >
                        <div
                            style={{
                                background: "#fafbfc",
                                border: "1px solid #e5e7eb",
                                borderRadius: "10px",
                                padding: "20px",
                                fontSize: "14px",
                                lineHeight: "1.6",
                            }}
                        >
                            <ReactMarkdown
                                remarkPlugins={[remarkGfm]}
                                components={{
                                    h1: ({ children, ...props }) => (
                                        <h1
                                            style={{
                                                fontSize: "20px",
                                                fontWeight: "bold",
                                                margin: "16px 0 8px 0",
                                                color: "#1f2937",
                                            }}
                                            {...props}
                                        >
                                            {children}
                                        </h1>
                                    ),
                                    h2: ({ children, ...props }) => (
                                        <h2
                                            style={{
                                                fontSize: "18px",
                                                fontWeight: "bold",
                                                margin: "14px 0 6px 0",
                                                color: "#1f2937",
                                            }}
                                            {...props}
                                        >
                                            {children}
                                        </h2>
                                    ),
                                    h3: ({ children, ...props }) => (
                                        <h3
                                            style={{
                                                fontSize: "16px",
                                                fontWeight: "bold",
                                                margin: "12px 0 6px 0",
                                                color: "#1f2937",
                                            }}
                                            {...props}
                                        >
                                            {children}
                                        </h3>
                                    ),
                                    p: (props) => (
                                        <p style={{ margin: "8px 0", color: "#374151" }} {...props} />
                                    ),
                                    strong: (props) => (
                                        <strong
                                            style={{ fontWeight: "bold", color: "#1f2937" }}
                                            {...props}
                                        />
                                    ),
                                    a: ({ href, children, ...props }) => (
                                        <a
                                            href={href}
                                            target="_blank"
                                            rel="noopener noreferrer"
                                            style={{
                                                color: "#2563eb",
                                                textDecoration: "underline",
                                            }}
                                            {...props}
                                        >
                                            {children}
                                        </a>
                                    ),
                                    ul: (props) => (
                                        <ul style={{ margin: "8px 0", paddingLeft: "20px" }} {...props} />
                                    ),
                                    ol: (props) => (
                                        <ol style={{ margin: "8px 0", paddingLeft: "20px" }} {...props} />
                                    ),
                                    li: (props) => (
                                        <li style={{ margin: "4px 0", color: "#374151" }} {...props} />
                                    ),
                                }}
                            >
                                {resources}
                            </ReactMarkdown>
                        </div>
                    </div>
                )}

                {/* Empty State */}
                {!loading && !resources && !error && (
                    <div
                        style={{
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            justifyContent: "center",
                            padding: "40px",
                            color: "#6b7280",
                            textAlign: "center",
                            flex: 1,
                        }}
                    >
                        <FiSearch size={48} style={{ marginBottom: "16px", opacity: 0.5 }} />
                        <p style={{ fontSize: "14px", margin: 0 }}>
                            Enter a topic to discover resources
                        </p>
                    </div>
                )}
            </div>

            <style>{`
        @keyframes spin {
          0% { transform: rotate(0deg); }
          100% { transform: rotate(360deg); }
        }
      `}</style>
        </Modal>
    );
}
