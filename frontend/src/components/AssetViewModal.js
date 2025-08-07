import React, { useState } from "react";
import { FiX, FiDownload, FiCopy } from "react-icons/fi";
import Modal from "./Modal";
import jsPDF from 'jspdf';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export default function AssetViewModal({ open, onClose, assetData }) {
  const [showCopyMessage, setShowCopyMessage] = useState(false);
  const [showDownloadMessage, setShowDownloadMessage] = useState(false);

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

  const handleDownload = () => {
    try {
      // Create PDF using jsPDF
      const pdf = new jsPDF();
      
      // Set font and size
      pdf.setFont('helvetica');
      pdf.setFontSize(12);
      
      // Add title
      pdf.setFontSize(20);
      pdf.setFont('helvetica', 'bold');
      pdf.text(assetData.asset_name, 20, 30);
      
      // Add metadata
      pdf.setFontSize(10);
      pdf.setFont('helvetica', 'normal');
      pdf.setTextColor(100, 100, 100);
      pdf.text(`Type: ${assetData.asset_type}`, 20, 45);
      pdf.text(`Category: ${assetData.asset_category}`, 20, 52);
      pdf.text(`Updated by: ${assetData.asset_last_updated_by}`, 20, 59);
      pdf.text(`Last updated: ${new Date(assetData.asset_last_updated_at).toLocaleString()}`, 20, 66);
      
      // Reset text color and start content
      pdf.setTextColor(0, 0, 0);
      pdf.setFontSize(12);
      
      // Parse and render markdown content
      const lines = assetData.asset_content.split('\n');
      let yPosition = 80;
      const lineHeight = 7;
      const pageWidth = 170;
      
      for (let i = 0; i < lines.length; i++) {
        const line = lines[i].trim();
        
        // Check if we need a new page
        if (yPosition > 270) {
          pdf.addPage();
          yPosition = 20;
        }
        
        // Process each line with proper markdown handling
        if (!line) {
          yPosition += lineHeight / 2;
          continue;
        }
        
        // Handle headers first
        if (line.startsWith('### ')) {
          pdf.setFontSize(16);
          pdf.setFont('helvetica', 'bold');
          pdf.text(line.substring(4), 20, yPosition);
          yPosition += lineHeight + 2;
          pdf.setFontSize(12);
          pdf.setFont('helvetica', 'normal');
          continue;
        }
        
        if (line.startsWith('## ')) {
          pdf.setFontSize(18);
          pdf.setFont('helvetica', 'bold');
          pdf.text(line.substring(3), 20, yPosition);
          yPosition += lineHeight + 3;
          pdf.setFontSize(12);
          pdf.setFont('helvetica', 'normal');
          continue;
        }
        
        if (line.startsWith('# ')) {
          pdf.setFontSize(20);
          pdf.setFont('helvetica', 'bold');
          pdf.text(line.substring(2), 20, yPosition);
          yPosition += lineHeight + 4;
          pdf.setFontSize(12);
          pdf.setFont('helvetica', 'normal');
          continue;
        }
        
        // Handle horizontal rules
        if (line.match(/^[-*_]{3,}$/)) {
          pdf.setDrawColor(200, 200, 200);
          pdf.line(20, yPosition, 190, yPosition);
          yPosition += lineHeight;
          continue;
        }
        
        // Handle blockquotes
        if (line.startsWith('> ')) {
          pdf.setFillColor(248, 250, 252);
          pdf.rect(15, yPosition - 3, pageWidth + 10, lineHeight + 6, 'F');
          pdf.setTextColor(100, 100, 100);
          pdf.setFont('helvetica', 'italic');
          pdf.text(line.substring(2), 20, yPosition);
          yPosition += lineHeight + 2;
          pdf.setTextColor(0, 0, 0);
          pdf.setFont('helvetica', 'normal');
          continue;
        }
        
        // Handle tables
        if (line.includes('|') && line.trim().startsWith('|') && line.trim().endsWith('|')) {
          const cells = line.split('|').map(cell => cell.trim()).filter(cell => cell);
          
          // Check if this is a table separator
          if (line.match(/^[|\s\-:]+$/)) {
            yPosition += 2;
            continue;
          }
          
          // Calculate column widths based on content
          const columnWidths = [];
          const totalWidth = pageWidth;
          
          // Define relative widths for different column types
          const relativeWidths = [];
          for (let j = 0; j < cells.length; j++) {
            const cellText = cells[j];
            // Determine column type based on content or position
            if (cellText.toLowerCase().includes('description') || 
                cellText.toLowerCase().includes('desc') ||
                cellText.length > 30) {
              relativeWidths.push(4); // Description column gets much more space
            } else if (cellText.toLowerCase().includes('name') || 
                       cellText.toLowerCase().includes('title') ||
                       cellText.length > 15) {
              relativeWidths.push(2.5); // Name column gets medium space
            } else if (cellText.toLowerCase().includes('bloom') ||
                       cellText.toLowerCase().includes('assessment')) {
              relativeWidths.push(2); // Medium space for these columns
            } else {
              relativeWidths.push(1.5); // Other columns get less space
            }
          }
          
          // Calculate actual widths
          const totalRelativeWidth = relativeWidths.reduce((sum, width) => sum + width, 0);
          for (let j = 0; j < cells.length; j++) {
            columnWidths.push((relativeWidths[j] / totalRelativeWidth) * totalWidth);
          }
          
          // Calculate row height first with better spacing
          let maxRowHeight = 0;
          for (let j = 0; j < cells.length; j++) {
            const cellText = cells[j];
            const cellWidth = columnWidths[j];
            const textLines = pdf.splitTextToSize(cellText, cellWidth - 10); // More padding
            const cellHeight = textLines.length * 6 + 10; // Increased line spacing (6px) and padding (10px)
            if (cellHeight > maxRowHeight) {
              maxRowHeight = cellHeight;
            }
          }
          
          // Track if this is the first row (header)
          const isHeaderRow = yPosition === 80 || yPosition === 87;
          
          // Draw the connected table grid
          pdf.setDrawColor(100, 100, 100);
          pdf.setLineWidth(0.5);
          
          // Draw horizontal lines for the row
          const rowTop = yPosition - 4;
          const rowBottom = yPosition + maxRowHeight + 6; // Extra space at bottom
          
          // Draw top horizontal line
          pdf.line(20, rowTop, 20 + totalWidth, rowTop);
          // Draw bottom horizontal line
          pdf.line(20, rowBottom, 20 + totalWidth, rowBottom);
          
          // Draw vertical lines
          let xPos = 20;
          for (let j = 0; j <= cells.length; j++) {
            pdf.line(xPos, rowTop, xPos, rowBottom);
            if (j < cells.length) {
              xPos += columnWidths[j];
            }
          }
          
          // Now add content to cells
          xPos = 20;
          for (let j = 0; j < cells.length; j++) {
            const cellText = cells[j];
            const cellWidth = columnWidths[j];
            
            // Handle header cells
            if (isHeaderRow) {
              pdf.setFillColor(240, 242, 245);
              pdf.rect(xPos, rowTop, cellWidth, maxRowHeight + 10, 'F'); // Match the extra space
            }
            
            // Add cell text
            pdf.setTextColor(0, 0, 0);
            if (isHeaderRow) {
              pdf.setFont('helvetica', 'bold');
            } else {
              pdf.setFont('helvetica', 'normal');
            }
            
            // Calculate text wrapping for this cell with more padding
            const textLines = pdf.splitTextToSize(cellText, cellWidth - 10);
            
            // Add text lines with improved positioning and spacing
            for (let k = 0; k < textLines.length; k++) {
              pdf.text(textLines[k], xPos + 5, yPosition + (k * 6) + 3); // 6px line spacing, 5px left margin, 3px top margin
            }
            
            xPos += cellWidth;
          }
          
          // Update y position based on the tallest cell in this row with extra space
          yPosition += maxRowHeight + 8; // Extra space between rows
          continue;
        }
        
        // Handle lists
        if (line.match(/^(\s*)[*\-+]\s/)) {
          const match = line.match(/^(\s*)[*\-+]\s(.+)$/);
          if (match) {
            const indent = match[1].length;
            const content = match[2];
            const bulletX = 20 + (indent * 2);
            const textX = bulletX + 8;
            
            // Draw bullet point
            pdf.setFillColor(0, 0, 0);
            pdf.circle(bulletX, yPosition - 1, 1, 'F');
            
            // Add text
            const textLines = pdf.splitTextToSize(content, pageWidth - (indent * 2) - 10);
            for (let k = 0; k < textLines.length; k++) {
              pdf.text(textLines[k], textX, yPosition + (k * 4));
            }
            yPosition += (textLines.length * 4) + 2;
            continue;
          }
        }
        
        // Handle numbered lists
        if (line.match(/^(\s*)\d+\.\s/)) {
          const match = line.match(/^(\s*)\d+\.\s(.+)$/);
          if (match) {
            const indent = match[1].length;
            const content = match[2];
            const numberX = 20 + (indent * 2);
            const textX = numberX + 12;
            
            // Add number
            pdf.setFont('helvetica', 'bold');
            pdf.text('•', numberX, yPosition);
            
            // Add text
            pdf.setFont('helvetica', 'normal');
            const textLines = pdf.splitTextToSize(content, pageWidth - (indent * 2) - 15);
            for (let k = 0; k < textLines.length; k++) {
              pdf.text(textLines[k], textX, yPosition + (k * 4));
            }
            yPosition += (textLines.length * 4) + 2;
            continue;
          }
        }
        
        // Handle text with ** markers - just remove them
        if (line.includes('**')) {
          const cleanLine = line.replace(/\*\*/g, '');
          const textLines = pdf.splitTextToSize(cleanLine, pageWidth);
          for (let k = 0; k < textLines.length; k++) {
            pdf.setFont('helvetica', 'normal');
            pdf.text(textLines[k], 20, yPosition + (k * 6));
          }
          yPosition += textLines.length * 6 + 2;
          continue;
        }
        
        // Handle inline code
        if (line.includes('`')) {
          const cleanLine = line.replace(/`([^`]+)`/g, '$1');
          const textLines = pdf.splitTextToSize(cleanLine, pageWidth);
          for (let k = 0; k < textLines.length; k++) {
            pdf.setFont('helvetica', 'normal');
            pdf.text(textLines[k], 20, yPosition + (k * 6));
          }
          yPosition += textLines.length * 6 + 2;
          continue;
        }
        
        // Regular text
        const textLines = pdf.splitTextToSize(line, pageWidth);
        for (let k = 0; k < textLines.length; k++) {
          pdf.setFont('helvetica', 'normal');
          pdf.text(textLines[k], 20, yPosition + (k * 6));
        }
        yPosition += textLines.length * 6 + 2;
      }
      
      // Add footer
      pdf.setFontSize(10);
      pdf.setTextColor(100, 100, 100);
      pdf.text(`Generated on ${new Date().toLocaleString()}`, 20, 280);
      
      // Save the PDF
      pdf.save(`${assetData.asset_name}.pdf`);

      setShowDownloadMessage(true);
      setTimeout(() => setShowDownloadMessage(false), 2000); // Hide after 2 seconds
    } catch (error) {
      console.error('Failed to download file:', error);
    }
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
            <button
              onClick={handleDownload}
              style={{
                background: '#2563eb',
                border: 'none',
                borderRadius: '6px',
                padding: '8px 12px',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '6px',
                fontSize: '14px',
                color: 'white',
                transition: 'all 0.2s ease'
              }}
              onMouseEnter={(e) => {
                e.currentTarget.style.background = '#1d4ed8';
              }}
              onMouseLeave={(e) => {
                e.currentTarget.style.background = '#2563eb';
              }}
              title="Download as PDF"
            >
              <FiDownload size={16} />
              Download
            </button>
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

            {/* Download confirmation message */}
            {showDownloadMessage && (
              <div style={{
                position: 'absolute',
                top: '-40px',
                left: '50%',
                transform: 'translateX(-50%)',
                background: '#2563eb',
                color: 'white',
                padding: '6px 12px',
                borderRadius: '6px',
                fontSize: '12px',
                fontWeight: 500,
                whiteSpace: 'nowrap',
                zIndex: 1000,
                animation: 'fadeInOut 2s ease-in-out'
              }}>
                ✓ Downloaded successfully!
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
            remarkPlugins={[remarkGfm]}
            components={{
              // Custom styling for markdown elements
              h1: (props) => <h1 style={{fontSize: '20px', fontWeight: 'bold', margin: '16px 0 8px 0', color: '#1f2937'}} {...props} />,
              h2: (props) => <h2 style={{fontSize: '18px', fontWeight: 'bold', margin: '14px 0 6px 0', color: '#1f2937'}} {...props} />,
              h3: (props) => <h3 style={{fontSize: '16px', fontWeight: 'bold', margin: '12px 0 6px 0', color: '#1f2937'}} {...props} />,
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
              a: (props) => <a style={{color: '#2563eb', textDecoration: 'underline'}} {...props} />,
              table: (props) => <table style={{borderCollapse: 'collapse', width: '100%', margin: '8px 0'}} {...props} />,
              th: (props) => <th style={{border: '1px solid #d1d5db', padding: '8px', background: '#f9fafb', fontWeight: 'bold'}} {...props} />,
              td: (props) => <td style={{border: '1px solid #d1d5db', padding: '8px'}} {...props} />
            }}
          >
            {assetData.asset_content}
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