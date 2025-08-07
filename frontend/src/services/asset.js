import axios from 'axios';
import jsPDF from 'jspdf';

const baseUrl = process.env.REACT_APP_API_BASE_URL || 'http://localhost:8000';
const API_BASE = new URL('/api', baseUrl).toString();

function getToken() {
  const token = localStorage.getItem('token');
  if (!token || token === 'null') {
    throw new Error('User not authenticated. Please log in.');
  }
  return token;
}

function handleAxiosError(error) {
  if (error.response && error.response.data && error.response.data.detail) {
    throw new Error(error.response.data.detail);
  }
  throw new Error(error.message || 'Unknown error');
}

export const assetService = {
  // Get all assets for a course
  getAssets: async (courseId) => {
    try {
      const res = await axios.get(`${API_BASE}/courses/${courseId}/assets`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`
        }
      });
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Create initial asset chat with selected files
  createAssetChat: async (courseId, assetTypeName, fileNames) => {
    try {
      const res = await axios.post(`${API_BASE}/courses/${courseId}/asset_chat/${assetTypeName}`, 
        { file_names: fileNames }, 
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
          }
        }
      );
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Continue asset chat conversation
  continueAssetChat: async (courseId, assetName, threadId, userPrompt) => {
    try {
      const res = await axios.put(`${API_BASE}/courses/${courseId}/asset_chat/${assetName}?thread_id=${threadId}`, 
        { user_prompt: userPrompt }, 
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
          }
        }
      );
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Save asset to database
  saveAsset: async (courseId, assetName, assetType, content) => {
    try {
      const res = await axios.post(`${API_BASE}/courses/${courseId}/assets`, 
        { content: content }, 
        {
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${getToken()}`
          },
          params: {
            asset_name: assetName,
            asset_type: assetType
          }
        }
      );
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // View asset content
  viewAsset: async (courseId, assetName) => {
    try {
      const res = await axios.get(`${API_BASE}/courses/${courseId}/assets/${assetName}/view`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`
        }
      });
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Download asset as PDF file
  downloadAsset: async (courseId, assetName) => {
    try {
      const res = await axios.get(`${API_BASE}/courses/${courseId}/assets/${assetName}/view`, {
        headers: {
          'Authorization': `Bearer ${getToken()}`
        }
      });
      
      // Create PDF using jsPDF
      const asset = res.data;
      const pdf = new jsPDF();
      
      // Function to convert markdown to plain text for PDF
      const markdownToPlainText = (markdown) => {
        if (!markdown) return '';
        
        let text = markdown;
        
        // Handle code blocks first (remove them completely)
        text = text.replace(/```[\s\S]*?```/g, '');
        
        // Handle tables - convert to simple text format
        text = text.replace(/\|(.+)\|/g, (match, content) => {
          // Split by | and clean up each cell
          const cells = content.split('|').map(cell => cell.trim()).filter(cell => cell);
          return cells.join(' | ');
        });
        
        // Remove table separators (lines with only |, -, and spaces)
        text = text.replace(/^\|[\s\-|:]+\|$/gm, '');
        
        // Handle headers - add spacing and emphasis
        text = text.replace(/^### (.*$)/gim, '\n$1\n');
        text = text.replace(/^## (.*$)/gim, '\n$1\n');
        text = text.replace(/^# (.*$)/gim, '\n$1\n');
        
        // Handle blockquotes - add spacing
        text = text.replace(/^> (.*$)/gim, '\n$1\n');
        
        // Handle lists - convert to bullet points with proper indentation
        text = text.replace(/^(\s*)\* (.*$)/gim, (match, spaces, content) => {
          const indent = spaces.length;
          const bullets = '  '.repeat(Math.floor(indent / 2)) + '• ';
          return bullets + content;
        });
        
        text = text.replace(/^(\s*)- (.*$)/gim, (match, spaces, content) => {
          const indent = spaces.length;
          const bullets = '  '.repeat(Math.floor(indent / 2)) + '• ';
          return bullets + content;
        });
        
        // Handle numbered lists
        text = text.replace(/^(\s*)\d+\. (.*$)/gim, (match, spaces, content) => {
          const indent = spaces.length;
          const bullets = '  '.repeat(Math.floor(indent / 2)) + '• ';
          return bullets + content;
        });
        
        // Handle bold and italic - remove formatting but keep text
        text = text.replace(/\*\*(.*?)\*\*/g, '$1');
        text = text.replace(/\*(.*?)\*/g, '$1');
        
        // Handle inline code - keep the content
        text = text.replace(/`([^`]+)`/g, '$1');
        
        // Handle links - keep the text, remove the URL
        text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
        
        // Handle images - keep alt text if available
        text = text.replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1');
        
        // Handle strikethrough
        text = text.replace(/~~(.*?)~~/g, '$1');
        
        // Handle horizontal rules
        text = text.replace(/^[\-\*_]{3,}$/gm, '\n' + '─'.repeat(50) + '\n');
        
        // Clean up extra whitespace and normalize line breaks
        text = text
          .replace(/\n\s*\n\s*\n/g, '\n\n') // Remove multiple consecutive empty lines
          .replace(/\n{3,}/g, '\n\n') // Limit to max 2 consecutive newlines
          .replace(/^\s+$/gm, '') // Remove lines with only whitespace
          .trim();
        
        return text;
      };
      
      // Set font and size
      pdf.setFont('helvetica');
      pdf.setFontSize(16);
      
      // Add title
      pdf.setFontSize(20);
      pdf.setFont('helvetica', 'bold');
      pdf.text(asset.asset_name, 20, 30);
      
      // Add metadata
      pdf.setFontSize(12);
      pdf.setFont('helvetica', 'normal');
      pdf.setTextColor(100, 100, 100);
      pdf.text(`Type: ${asset.asset_type}`, 20, 45);
      pdf.text(`Category: ${asset.asset_category}`, 20, 52);
      pdf.text(`Updated by: ${asset.asset_last_updated_by}`, 20, 59);
      pdf.text(`Last updated: ${new Date(asset.asset_last_updated_at).toLocaleString()}`, 20, 66);
      
      // Reset text color and add content
      pdf.setTextColor(0, 0, 0);
      pdf.setFontSize(12);
      
      // Convert markdown to plain text for PDF
      const plainTextContent = markdownToPlainText(asset.asset_content);
      
      // Split content into lines that fit the page width
      const maxWidth = 170; // Page width minus margins
      const lines = pdf.splitTextToSize(plainTextContent, maxWidth);
      
      // Add content starting from y position 80
      let yPosition = 80;
      const lineHeight = 7;
      
      for (let i = 0; i < lines.length; i++) {
        // Check if we need a new page
        if (yPosition > 270) {
          pdf.addPage();
          yPosition = 20;
        }
        
        pdf.text(lines[i], 20, yPosition);
        yPosition += lineHeight;
      }
      
      // Add footer
      pdf.setFontSize(10);
      pdf.setTextColor(100, 100, 100);
      pdf.text(`Generated on ${new Date().toLocaleString()}`, 20, 280);
      
      // Save the PDF
      pdf.save(`${assetName}.pdf`);
      
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  }
}; 