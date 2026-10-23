import React, { useState } from "react";
import { FiX, FiCopy } from "react-icons/fi";
import Modal from "./Modal";
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkBreaks from 'remark-breaks';
import { viewResource } from "../services/resources";
import DownloadButton from "./DownloadButton";
import { latexToText } from "../utils/latexToText";

export default function ResourceViewModal({ open, onClose, resourceName, courseId }) {
  const [showCopyMessage, setShowCopyMessage] = useState(false);
  const [resourceData, setResourceData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [pdfUrl, setPdfUrl] = useState(null);
  const isPdf = !!resourceName && resourceName.toLowerCase().endsWith('.pdf');
  // Mirrors the backend's IMAGE_EXTENSIONS (pdf_image_extractor.is_image_filename)
  const isImage = !!resourceName && /\.(png|jpe?g|gif|bmp|tiff?|webp)$/i.test(resourceName);

  // Image resources have no text content; their bytes are stored in Mongo and
  // served by GET /courses/{id}/images/{image_id}, where the id is the backend's
  // resource_image_id slug: "res_" + non-alphanumerics collapsed to "_".
  const apiBase = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
  const imageSlug = (resourceName || '').replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '') || 'image';
  const imageUrl = isImage && courseId
    ? `${apiBase}/api/courses/${courseId}/images/res_${imageSlug}`
    : null;

  React.useEffect(() => {
    if (!(open && resourceName && courseId)) return;
    let objectUrl = null;

    const fetchText = async () => {
      setLoading(true);
      setError(null);
      try {
        const data = await viewResource(courseId, resourceName);
        setResourceData(data);
      } catch (error) {
        setError(error.message || 'Failed to load resource content');
      } finally {
        setLoading(false);
      }
    };

    // For a PDF resource, show the real file if its bytes are stored (new upload
    // flow); otherwise fall back to the extracted-text view (old upload flow).
    const loadPdf = async () => {
      setLoading(true);
      setError(null);
      try {
        const base = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
        const url = `${base}/api/courses/${courseId}/resources/${encodeURIComponent(resourceName)}/pdf`;
        const res = await fetch(url);
        if (res.ok) {
          const blob = await res.blob();
          objectUrl = URL.createObjectURL(blob);
          setPdfUrl(objectUrl);
          setLoading(false);
        } else {
          await fetchText();
        }
      } catch (e) {
        await fetchText();
      }
    };

    setPdfUrl(null);
    setResourceData(null);
    if (isPdf) {
      loadPdf();
    } else if (isImage) {
      // The <img> tag fetches the bytes itself; nothing to preload here.
      setError(null);
      setLoading(false);
    } else {
      fetchText();
    }

    return () => {
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [open, resourceName, courseId, isPdf, isImage]);

  const handleCopyContent = async () => {
    if (!resourceData?.content) return;
    
    try {
      await navigator.clipboard.writeText(resourceData.content);
      setShowCopyMessage(true);
      setTimeout(() => setShowCopyMessage(false), 2000);
    } catch (error) {
      console.error('Failed to copy to clipboard:', error);
    }
  };

  if (!open) return null;

  return (
    <Modal
      open={open}
      onClose={onClose}
      modalStyle={isPdf ? { width: 'min(1150px, 95vw)', maxWidth: '95vw', minWidth: 0, padding: '16px' } : undefined}
    >
      <div style={{
        position: 'relative',
        maxHeight: '90vh',
        overflow: 'hidden',
        display: 'flex',
        flexDirection: 'column'
      }}>
        {/* Header */}
        <div style={{
          paddingBottom: '20px',
          borderBottom: '1px solid #e5e7eb',
          marginBottom: '20px',
          flexShrink: 0
        }}>
          <div style={{
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'flex-start'
          }}>
            <div>
              <h2 style={{ 
                margin: 0,
                fontSize: '24px',
                fontWeight: 700,
                color: '#1f2937'
              }}>
                {resourceName || 'Resource'}
              </h2>
            </div>
            
            {/* Action buttons */}
            <div style={{
              display: 'flex',
              gap: '8px',
              position: 'relative'
            }}>
              {/* Only show buttons if there's content and no error */}
              {!error && resourceData?.content && (
                <>
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
                    {showCopyMessage && (
                      <span style={{ 
                        fontSize: '12px', 
                        color: '#374151',
                        marginLeft: '4px'
                      }}>
                        ✓ Copied!
                      </span>
                    )}
                  </button>
                  <DownloadButton
                    courseId={courseId}
                    filename={resourceName}
                    content={resourceData.content}
                  />
                </>
              )}
              
              {/* Close Button - Always visible */}
              <button
                onClick={onClose}
                style={{
                  background: 'transparent',
                  border: 'none',
                  cursor: 'pointer',
                  padding: '8px',
                  borderRadius: '6px',
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
            </div>
          </div>
        </div>


        {/* Content */}
        <div style={{ 
          flex: 1, 
          overflow: 'auto',
          padding: '0 4px'
        }}>
          {loading && (
            <div style={{ 
              display: 'flex', 
              justifyContent: 'center', 
              alignItems: 'center',
              height: '200px',
              color: '#6b7280'
            }}>
              Loading resource content...
            </div>
          )}

          {error && (
            <div style={{ 
              display: 'flex', 
              justifyContent: 'center', 
              alignItems: 'center',
              height: '200px',
              color: '#dc2626',
              textAlign: 'center',
              padding: '20px'
            }}>
              <div>
                <div style={{ fontSize: '16px', fontWeight: '500', marginBottom: '8px' }}>
                  {/* {error} */}
                </div>
                <div style={{ fontSize: '14px', color: '#6b7280' }}>
                  Resources uploaded by you can't be viewed
                </div>
              </div>
            </div>
          )}

          {imageUrl && !loading && !error && (
            <div style={{
              display: 'flex',
              justifyContent: 'center',
              background: '#fafbfc',
              border: '1px solid #e5e7eb',
              borderRadius: '8px',
              padding: '16px',
              maxHeight: '75vh',
              overflow: 'auto'
            }}>
              <img
                src={imageUrl}
                alt={resourceName}
                style={{ maxWidth: '100%', height: 'auto', borderRadius: '4px' }}
                onError={() => setError('Failed to load image')}
              />
            </div>
          )}

          {pdfUrl && !loading && (
            <iframe
              src={pdfUrl}
              title={resourceName}
              style={{ width: '100%', height: '82vh', border: '1px solid #e5e7eb', borderRadius: '8px', display: 'block', background: '#f3f4f6' }}
            />
          )}

          {resourceData?.content && !loading && !error && !pdfUrl && (
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
                  p: (props) => <p style={{margin: '8px 0', color: '#374151'}} {...props} />,
                  strong: (props) => <strong style={{fontWeight: 'bold', color: '#1f2937'}} {...props} />,
                  em: (props) => <em style={{fontStyle: 'italic', color: '#374151'}} {...props} />,
                  code: ({inline, ...props}) => 
                    inline ? 
                      <code style={{background: '#f3f4f6', padding: '2px 4px', borderRadius: '3px', fontFamily: 'monospace', fontSize: '13px'}} {...props} /> :
                      <code style={{background: '#f3f4f6', padding: '8px', borderRadius: '6px', fontFamily: 'monospace', fontSize: '13px', display: 'block', margin: '8px 0'}} {...props} />,
                  ul: (props) => <ul style={{margin: '8px 0', paddingLeft: '20px'}} {...props} />,
                  ol: (props) => <ol style={{margin: '8px 0', paddingLeft: '20px'}} {...props} />,
                  li: (props) => <li style={{margin: '4px 0', color: '#374151'}} {...props} />,
                  blockquote: (props) => <blockquote style={{borderLeft: '4px solid #2563eb', paddingLeft: '12px', margin: '8px 0', color: '#6b7280', fontStyle: 'italic'}} {...props} />,
                  a: ({href, children, ...props}) => <a href={href} target="_blank" rel="noopener noreferrer" style={{color: '#2563eb', textDecoration: 'underline'}} {...props}>{children}</a>,
                  table: (props) => <table style={{borderCollapse: 'collapse', width: '100%', margin: '8px 0'}} {...props} />,
                  th: (props) => <th style={{border: '1px solid #d1d5db', padding: '8px', background: '#f9fafb', fontWeight: 'bold'}} {...props} />,
                  td: (props) => <td style={{border: '1px solid #d1d5db', padding: '8px'}} {...props} />
                }}
              >
                {latexToText(resourceData.content)}
              </ReactMarkdown>
            </div>
          )}
        </div>
      </div>
    </Modal>
  );
}
