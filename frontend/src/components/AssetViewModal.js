import React, { useEffect, useState } from "react";
import { FiX, FiCopy } from "react-icons/fi";
import Modal from "./Modal";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import DownloadButton from "./DownloadButton";
import { latexToText } from "../utils/latexToText";
import { API_BASE } from "../utils/axiosConfig";
import { isSprintStructure, sprintStructureComponents } from "../utils/sprintStructure";

// Resolve internal /courses/.../images/... URLs to authenticated object URLs
function useResolvedImageSrc(src) {
  const [resolvedSrc, setResolvedSrc] = useState(src);
  useEffect(() => {
    if (!src) return;
    if (src.startsWith('/courses/') && src.includes('/images/')) {
      const fullUrl = `${API_BASE}${src}`;
      const token = (() => {
        try { return JSON.parse(localStorage.getItem('user') || '{}').token || ''; } catch { return ''; }
      })();
      fetch(fullUrl, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
        .then(r => r.ok ? r.blob() : null)
        .then(blob => { if (blob) setResolvedSrc(URL.createObjectURL(blob)); })
        .catch(() => {});
    } else {
      setResolvedSrc(src);
    }
  }, [src]);
  return resolvedSrc;
}

function ResolvedImage({ src, alt, style }) {
  const resolved = useResolvedImageSrc(src);
  return <img src={resolved} alt={alt || ''} loading="lazy" style={style} />;
}

// Helper to clean <br> tags and ensure sub-questions (a), (b), (c), (i), (ii) have 
// a clean 1-line gap between them when rendered in table cells or paragraphs.
function renderFormattedContent(nodes) {
  if (nodes === null || nodes === undefined) return null;
  if (typeof nodes === "string") {
    // Convert all literal <br> variants to \n
    let cleaned = nodes.replace(/&lt;br\s*\/?&gt;|<br\s*\/?>/gi, "\n");
    
    // Ensure sub-questions like (a), (b), (c), (i), (ii) have a line break before them if following text
    cleaned = cleaned.replace(
      /(?:\s+|\n|^)(\((?:[a-z]|\d+|[ivx]+)\)\s+)/gi,
      (match, p1, offset) => (offset === 0 ? p1 : `\n\n${p1.trimStart()}`)
    );

    const lines = cleaned.split(/\n+/).map(l => l.trim()).filter(Boolean);
    if (lines.length <= 1) {
      return lines[0] !== undefined ? lines[0] : "";
    }
    return lines.map((line, idx) => (
      <div
        key={idx}
        style={{
          marginTop: idx > 0 ? "10px" : "0",
          lineHeight: "1.5"
        }}
      >
        {line}
      </div>
    ));
  }

  if (Array.isArray(nodes)) {
    return nodes.map((child, idx) => {
      if (typeof child === "string") {
        return <React.Fragment key={idx}>{renderFormattedContent(child)}</React.Fragment>;
      }
      return <React.Fragment key={idx}>{child}</React.Fragment>;
    });
  }

  return nodes;
}

export default function AssetViewModal({ open, onClose, assetData, courseId }) {
  const [showCopyMessage, setShowCopyMessage] = useState(false);

  if (!open || !assetData) return null;

  const handleCopyContent = async () => {
    try {
      await navigator.clipboard.writeText(assetData.asset_content);
      setShowCopyMessage(true);
      setTimeout(() => setShowCopyMessage(false), 2000); // Hide after 2 seconds
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
    }
  };

  // Build the content to download.
  const buildDownloadContent = () => {
    const content = assetData.asset_content;

    // Type/Category metadata injection is disabled for now.
    // const assetType = assetData.asset_type || '';
    // const assetCategory = assetData.asset_category || '';
    //
    // if (assetType || assetCategory) {
    //   const metadataLines = [];
    //   if (assetType) {
    //     metadataLines.push(`- **Type:** ${assetType}`);
    //   }
    //   if (assetCategory) {
    //     metadataLines.push(`- **Category:** ${assetCategory}`);
    //   }
    //
    //   const metadataText = metadataLines.join('\n');
    //
    //   // Find Duration line and insert after it
    //   if (content.includes('Duration:')) {
    //     const lines = content.split('\n');
    //     for (let i = 0; i < lines.length; i++) {
    //       if (lines[i].includes('Duration:')) {
    //         lines.splice(i + 1, 0, metadataText);
    //         break;
    //       }
    //     }
    //     content = lines.join('\n');
    //   } else {
    //     // If no Duration found, prepend to content
    //     content = metadataText + '\n\n' + content;
    //   }
    // }

    return content;
  };

  return (
    <Modal open={open} onClose={onClose}>
      <div style={{ width: '100%', maxWidth: '800px', maxHeight: '80vh' }}>
        {/* Header */}
        <div style={{
          display: 'flex',
          justifyContent: 'space-between',
          alignItems: 'center',
          marginBottom: '24px',
          paddingBottom: '16px',
          borderBottom: '1px solid #e5e7eb'
        }}>
          <div>
            <h2 style={{
              margin: 0,
              fontSize: '24px',
              fontWeight: 700,
              color: '#1f2937'
            }}>
              {assetData.asset_name}
            </h2>
            <div style={{
              display: 'flex',
              gap: '16px',
              marginTop: '8px',
              fontSize: '14px',
              color: '#6b7280'
            }}>
              <span>Type: {assetData.asset_type}</span>
              <span>Category: {assetData.asset_category}</span>
              <span>Updated by: {assetData.asset_last_updated_by}</span>
            </div>
          </div>
          
          {/* Action buttons */}
          <div style={{
            display: 'flex',
            gap: '8px',
            position: 'relative'
          }}>
            <button
              onClick={handleCopyContent}
              style={{
                background: '#f3f4f6',
                border: '1px solid #d1d5db',
                borderRadius: '6px',
                padding: '8px 12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '14px',
                color: '#374151',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#e5e7eb';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = '#f3f4f6';
              }}
              title="Copy content"
            >
              <FiCopy size={16} />
              Copy
            </button>
            <DownloadButton
              courseId={courseId}
              filename={assetData.asset_name}
              content={buildDownloadContent}
            />
            <button
              onClick={onClose}
              style={{
                background: 'transparent',
                border: 'none',
                borderRadius: '6px',
                padding: '8px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: '#6b7280',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#f3f4f6';
                e.currentTarget.style.color = '#374151';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = 'transparent';
                e.currentTarget.style.color = '#6b7280';
              }}
              title="Close"
            >
              <FiX size={20} />
            </button>

            {/* Copy confirmation message */}
            {showCopyMessage && (
              <div style={{
                position: 'absolute',
                top: '-40px',
                left: '50%',
                transform: 'translateX(-50%)',
                background: '#10b981',
                color: 'white',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 500,
                whiteSpace: 'nowrap',
                zIndex: 1000,
                animation: 'fadeInOut 2s ease-in-out'
              }}>
                ✓ Copied to clipboard!
              </div>
            )}
          </div>
        </div>

        {/* Content with Markdown Rendering */}
        <div style={{
          background: '#fafbfc',
          border: '1px solid #e5e7eb',
          borderRadius: '8px',
          padding: '20px',
          maxHeight: '60vh',
          overflowY: 'auto',
          fontSize: '14px',
          lineHeight: '1.6'
        }}>
          <ReactMarkdown 
            remarkPlugins={[remarkGfm, remarkBreaks]}
            components={{
              // Custom styling for markdown elements
              h1: ({children, ...props}) => {
                // Only render if there's content
                if (!children || (Array.isArray(children) && children.every(child => !child))) {
                  return null;
                }
                return <h1 style={{fontSize: '20px', fontWeight: 'bold', margin: '16px 0 8px 0', color: '#1f2937'}} {...props}>{children}</h1>;
              },
              h2: ({children, ...props}) => {
                // Only render if there's content
                if (!children || (Array.isArray(children) && children.every(child => !child))) {
                  return null;
                }
                return <h2 style={{fontSize: '18px', fontWeight: 'bold', margin: '14px 0 6px 0', color: '#1f2937'}} {...props}>{children}</h2>;
              },
              h3: ({children, ...props}) => {
                // Only render if there's content
                if (!children || (Array.isArray(children) && children.every(child => !child))) {
                  return null;
                }
                return <h3 style={{fontSize: '16px', fontWeight: 'bold', margin: '12px 0 6px 0', color: '#1f2937'}} {...props}>{children}</h3>;
              },
              p: ({children, ...props}) => <div style={{margin: '8px 0', color: '#374151', lineHeight: '1.6'}} {...props}>{renderFormattedContent(children)}</div>,
              strong: (props) => <strong style={{fontWeight: 'bold', color: '#1f2937'}} {...props} />,
              em: (props) => <em style={{fontStyle: 'italic', color: '#374151'}} {...props} />,
              code: ({inline, ...props}) => 
                inline ? 
                  <code style={{background: '#f3f4f6', padding: '2px 4px', borderRadius: '3px', fontFamily: 'monospace', fontSize: '13px'}} {...props} /> :
                  <code style={{background: '#f3f4f6', padding: '8px', borderRadius: '6px', fontFamily: 'monospace', fontSize: '13px', display: 'block', margin: '8px 0'}} {...props} />,
              ul: (props) => <ul style={{margin: '8px 0', paddingLeft: '20px'}} {...props} />,
              ol: (props) => <ol style={{margin: '8px 0', paddingLeft: '20px'}} {...props} />,
              li: ({ordered, ...props}) => <li style={{margin: ordered ? '12px 0' : '4px 0', color: '#374151'}} {...props} />,
              blockquote: (props) => <blockquote style={{borderLeft: '4px solid #2563eb', paddingLeft: '12px', margin: '8px 0', color: '#6b7280', fontStyle: 'italic'}} {...props} />,
              a: ({href, children, ...props}) => <a href={href} target="_blank" rel="noopener noreferrer" style={{color: '#2563eb', textDecoration: 'underline'}} {...props}>{children}</a>,
              table: (props) => <table style={{borderCollapse: 'collapse', width: '100%', margin: '8px 0'}} {...props} />,
              th: ({children, ...props}) => <th style={{border: '1px solid #d1d5db', padding: '10px 8px', background: '#f9fafb', fontWeight: 'bold'}} {...props}>{renderFormattedContent(children)}</th>,
              td: ({children, ...props}) => <td style={{border: '1px solid #d1d5db', padding: '10px 8px', verticalAlign: 'top', lineHeight: '1.5'}} {...props}>{renderFormattedContent(children)}</td>,
              img: ({src, alt}) => <ResolvedImage src={src} alt={alt} style={{maxWidth: '100%', height: 'auto', display: 'block', margin: '8px auto', borderRadius: '8px', border: '1px solid #eee'}} />,
              // Sprint Structure timetables keep their activity colour-coding here too.
              ...(isSprintStructure(assetData.asset_type) ? sprintStructureComponents : {})
            }}
          >
            {latexToText(assetData.asset_content)}
          </ReactMarkdown>
        </div>

        {/* Footer */}
        <div style={{
          marginTop: '16px',
          paddingTop: '16px',
          borderTop: '1px solid #e5e7eb',
          fontSize: '12px',
          color: '#6b7280',
          textAlign: 'center'
        }}>
          Last updated: {new Date(assetData.asset_last_updated_at).toLocaleString()}
        </div>
      </div>

      {/* CSS for animation */}
      <style>{`
        @keyframes fadeInOut {
          0% { opacity: 0; transform: translateX(-50%) translateY(-10px); }
          20% { opacity: 1; transform: translateX(-50%) translateY(0); }
          80% { opacity: 1; transform: translateX(-50%) translateY(0); }
          100% { opacity: 0; transform: translateX(-50%) translateY(-10px); }
        }
      `}</style>
    </Modal>
  );
} 