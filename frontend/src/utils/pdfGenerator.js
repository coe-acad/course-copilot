import jsPDF from 'jspdf';

// PDF Generator utility for chat responses
export const generatePDFFromText = (text, filename = 'chat-response.pdf') => {
  // Create a new document
  const doc = document.implementation.createHTMLDocument();
  
  // Add content to the document
  doc.body.innerHTML = `
    <div style="font-family: Arial, sans-serif; max-width: 800px; margin: 0 auto; padding: 20px;">
      <h1 style="color: #1976d2; border-bottom: 2px solid #1976d2; padding-bottom: 10px;">
        Chat Response
      </h1>
      <div style="background: #f5f5f5; padding: 20px; border-radius: 8px; margin: 20px 0;">
        <p style="margin: 0; line-height: 1.6; white-space: pre-wrap;">${text}</p>
      </div>
      <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #ddd; color: #666; font-size: 12px;">
        <p>Generated on: ${new Date().toLocaleString()}</p>
      </div>
    </div>
  `;

  // Convert to PDF using browser's print functionality
  const printWindow = window.open('', '_blank');
  printWindow.document.write(`
    <html>
      <head>
        <title>${filename}</title>
        <style>
          body { font-family: Arial, sans-serif; }
          @media print {
            body { margin: 0; }
          }
        </style>
      </head>
      <body>${doc.body.innerHTML}</body>
    </html>
  `);
  printWindow.document.close();
  
  // Wait for content to load then print
  printWindow.onload = () => {
    printWindow.print();
    printWindow.close();
  };
};

// Generate PDF using jsPDF with improved formatting
export const generatePDFWithJsPDF = (text, filename = 'chat-response.pdf', title = 'Chat Response', courseName = '', assetType = '') => {
  const doc = new jsPDF();
  
  // Set font
  doc.setFont('helvetica');
  
  // Add header with course name and asset type
  doc.setFontSize(14);
  doc.setTextColor(25, 118, 210); // #1976d2
  doc.text(title, 20, 20);
  
  // Add course name if provided
  if (courseName) {
    doc.setFontSize(12);
    doc.setTextColor(100, 100, 100);
    doc.text(`Course: ${courseName}`, 20, 30);
  }
  
  // Add asset type if provided
  if (assetType) {
    doc.setFontSize(12);
    doc.setTextColor(100, 100, 100);
    doc.text(`Type: ${assetType}`, 20, 37);
  }
  
  // Add line under header
  doc.setDrawColor(25, 118, 210);
  const lineY = assetType ? 42 : courseName ? 35 : 25;
  doc.line(20, lineY, 190, lineY);
  
  // Add content with improved formatting
  doc.setFontSize(11);
  doc.setTextColor(0, 0, 0);
  
  // Clean and format the text
  const cleanText = text
    .replace(/\n\s*\n/g, '\n') // Remove multiple empty lines
    .replace(/\s+/g, ' ') // Normalize whitespace
    .trim();
  
  // Split text into lines that fit the page width
  const maxWidth = 170; // Page width minus margins
  const lines = doc.splitTextToSize(cleanText, maxWidth);
  
  let yPosition = lineY + 15;
  const lineHeight = 6;
  
  // Add content lines with better spacing
  for (let i = 0; i < lines.length; i++) {
    // Check if we need a new page
    if (yPosition > 270) {
      doc.addPage();
      yPosition = 20;
    }
    doc.text(lines[i], 20, yPosition);
    yPosition += lineHeight;
  }
  
  // Add footer
  doc.setFontSize(9);
  doc.setTextColor(128, 128, 128);
  doc.text(`Generated on: ${new Date().toLocaleString()}`, 20, 280);
  
  // Save the PDF
  doc.save(filename);
};

// Create a blob from text content for download
export const createTextBlob = (text, filename = 'chat-response.txt') => {
  const blob = new Blob([text], { type: 'text/plain' });
  const url = URL.createObjectURL(blob);
  
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
};

// Create a PDF blob using jsPDF with improved formatting
export const createPDFBlob = (text, filename = 'chat-response.pdf', title = 'Chat Response', courseName = '', assetType = '') => {
  const doc = new jsPDF();
  
  // Set font
  doc.setFont('helvetica');
  
  // Add header with course name and asset type
  doc.setFontSize(14);
  doc.setTextColor(25, 118, 210); // #1976d2
  doc.text(title, 20, 20);
  
  // Add course name if provided
  if (courseName) {
    doc.setFontSize(12);
    doc.setTextColor(100, 100, 100);
    doc.text(`Course: ${courseName}`, 20, 30);
  }
  
  // Add asset type if provided
  if (assetType) {
    doc.setFontSize(12);
    doc.setTextColor(100, 100, 100);
    doc.text(`Type: ${assetType}`, 20, 37);
  }
  
  // Add line under header
  doc.setDrawColor(25, 118, 210);
  const lineY = assetType ? 42 : courseName ? 35 : 25;
  doc.line(20, lineY, 190, lineY);
  
  // Add content with improved formatting
  doc.setFontSize(11);
  doc.setTextColor(0, 0, 0);
  
  // Clean and format the text
  const cleanText = text
    .replace(/\n\s*\n/g, '\n') // Remove multiple empty lines
    .replace(/\s+/g, ' ') // Normalize whitespace
    .trim();
  
  // Split text into lines that fit the page width
  const maxWidth = 170; // Page width minus margins
  const lines = doc.splitTextToSize(cleanText, maxWidth);
  
  let yPosition = lineY + 15;
  const lineHeight = 6;
  
  // Add content lines with better spacing
  for (let i = 0; i < lines.length; i++) {
    // Check if we need a new page
    if (yPosition > 270) {
      doc.addPage();
      yPosition = 20;
    }
    doc.text(lines[i], 20, yPosition);
    yPosition += lineHeight;
  }
  
  // Add footer
  doc.setFontSize(9);
  doc.setTextColor(128, 128, 128);
  doc.text(`Generated on: ${new Date().toLocaleString()}`, 20, 280);
  
  // Save the PDF
  doc.save(filename);
};

// Create a PDF blob for upload to resources with improved formatting
export const createPDFBlobForUpload = (text, filename = 'chat-response.pdf', title = 'Chat Response', courseName = '', assetType = '') => {
  const doc = new jsPDF();
  
  // Set font
  doc.setFont('helvetica');
  
  // Add header with course name and asset type
  doc.setFontSize(14);
  doc.setTextColor(25, 118, 210); // #1976d2
  doc.text(title, 20, 20);
  
  // Add course name if provided
  if (courseName) {
    doc.setFontSize(12);
    doc.setTextColor(100, 100, 100);
    doc.text(`Course: ${courseName}`, 20, 30);
  }
  
  // Add asset type if provided
  if (assetType) {
    doc.setFontSize(12);
    doc.setTextColor(100, 100, 100);
    doc.text(`Type: ${assetType}`, 20, 37);
  }
  
  // Add line under header
  doc.setDrawColor(25, 118, 210);
  const lineY = assetType ? 42 : courseName ? 35 : 25;
  doc.line(20, lineY, 190, lineY);
  
  // Add content with improved formatting
  doc.setFontSize(11);
  doc.setTextColor(0, 0, 0);
  
  // Clean and format the text
  const cleanText = text
    .replace(/\n\s*\n/g, '\n') // Remove multiple empty lines
    .replace(/\s+/g, ' ') // Normalize whitespace
    .trim();
  
  // Split text into lines that fit the page width
  const maxWidth = 170; // Page width minus margins
  const lines = doc.splitTextToSize(cleanText, maxWidth);
  
  let yPosition = lineY + 15;
  const lineHeight = 6;
  
  // Add content lines with better spacing
  for (let i = 0; i < lines.length; i++) {
    // Check if we need a new page
    if (yPosition > 270) {
      doc.addPage();
      yPosition = 20;
    }
    doc.text(lines[i], 20, yPosition);
    yPosition += lineHeight;
  }
  
  // Add footer
  doc.setFontSize(9);
  doc.setTextColor(128, 128, 128);
  doc.text(`Generated on: ${new Date().toLocaleString()}`, 20, 280);
  
  // Return the PDF as a blob
  return doc.output('blob');
}; 