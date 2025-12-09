import axiosInstance from '../utils/axiosConfig';
import jsPDF from 'jspdf';


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
      const res = await axiosInstance.get(`/courses/${courseId}/assets`);
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Create initial asset chat with selected files (async with polling)
  createAssetChat: async (courseId, assetTypeName, fileNames) => {
    try {
      // Start the background task
      const res = await axiosInstance.post(`/courses/${courseId}/asset_chat/${assetTypeName}`, 
        { file_names: fileNames }
      );
      const taskData = res.data; // { task_id, status, message }
      
      // Poll for completion
      return await assetService.pollTaskUntilComplete(taskData.task_id);
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Continue asset chat conversation (async with polling)
  continueAssetChat: async (courseId, assetName, threadId, userPrompt) => {
    try {
      // Start the background task
      const res = await axiosInstance.put(`/courses/${courseId}/asset_chat/${assetName}?thread_id=${threadId}`, 
        { user_prompt: userPrompt }
      );
      const taskData = res.data; // { task_id, status, message }
      
      // Poll for completion
      return await assetService.pollTaskUntilComplete(taskData.task_id);
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Poll task status until completion
  pollTaskUntilComplete: async (taskId, maxAttempts = 180, intervalMs = 1000) => {
    let attempts = 0;
    
    while (attempts < maxAttempts) {
      try {
        const statusRes = await axiosInstance.get(`/tasks/${taskId}`);
        const taskStatus = statusRes.data; // { task_id, status, result, error }
        
        if (taskStatus.status === 'completed') {
          // Return result in the same format as before
          return taskStatus.result; // { response, thread_id }
        } else if (taskStatus.status === 'failed') {
          throw new Error(taskStatus.error || 'Task failed');
        } else if (taskStatus.status === 'cancelled') {
          throw new Error('Task was cancelled');
        }
        
        // Status is 'pending' or 'processing', wait and retry
        await new Promise(resolve => setTimeout(resolve, intervalMs));
        attempts++;
      } catch (error) {
        if (error.response && error.response.status === 404) {
          throw new Error('Task not found');
        }
        throw error;
      }
    }
    
    // Timeout after maxAttempts
    throw new Error('Task polling timeout - operation is taking longer than expected');
  },

  // Get task status (for checking without polling)
  getTaskStatus: async (taskId) => {
    try {
      const res = await axiosInstance.get(`/tasks/${taskId}`);
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Cancel a running task
  cancelTask: async (taskId) => {
    try {
      const res = await axiosInstance.delete(`/tasks/${taskId}`);
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Save asset to database
  saveAsset: async (courseId, assetName, assetType, content) => {
    try {
      const res = await axiosInstance.post(`/courses/${courseId}/assets`, 
        { content: content }, 
        {
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
      const res = await axiosInstance.get(`/courses/${courseId}/assets/${assetName}/view`);
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Download asset by streaming the backend text-to-pdf endpoint
  downloadAsset: async (courseId, assetName, contentOverride = null) => {
    try {
      if (!courseId || !assetName) {
        throw new Error('Course ID and Asset Name are required');
      }

      let content = contentOverride;
      let resolvedName = assetName;

      if (!content) {
        const res = await axiosInstance.get(`/courses/${courseId}/assets/${assetName}/view`);
        const asset = res.data;

        if (!asset || !asset.asset_content) {
          throw new Error('Invalid asset data received from server');
        }

        content = asset.asset_content;
        resolvedName = asset.asset_name || assetName;
      }

      const filename = `${resolvedName}.pdf`;

      const response = await axiosInstance.post(
        `/courses/${courseId}/assets/pdf`,
        { content, filename, asset_name: assetName },
        { responseType: 'blob' }
      );

      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Generate a PDF from raw markdown/text content using backend text_to_pdf utility
  downloadContentAsPdf: async (title, content, meta = {}) => {
    try {
      const courseId = localStorage.getItem('currentCourseId');
      if (!courseId) {
        throw new Error('No course ID found');
      }

      const filename = `${title || 'asset'}.pdf`;

      // Use backend text_to_pdf endpoint
      const response = await axiosInstance.post(
        `/courses/${courseId}/assets/pdf`,
        { content, filename },
        { responseType: 'blob' }
      );

      const blob = new Blob([response.data], { type: 'application/pdf' });
      const url = window.URL.createObjectURL(blob);
      const link = document.createElement('a');
      link.href = url;
      link.setAttribute('download', filename);
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      window.URL.revokeObjectURL(url);
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // OLD FRONTEND IMPLEMENTATION - REMOVED TO USE BACKEND text_to_pdf
  // Generate a PDF Blob from raw markdown/text content with the same styling as downloadContentAsPdf
  generateContentPdfBlob_OLD: async (title, content, meta = {}) => {
    try {
      const pdf = new jsPDF();

      class MarkdownToPDF {
        constructor(pdf) {
          this.pdf = pdf;
          this.margin = 20;
          const pageWidth = this.pdf.internal.pageSize.getWidth();
          const pageHeight = this.pdf.internal.pageSize.getHeight();
          this.pageWidth = pageWidth;
          this.pageHeight = pageHeight - 20;
          this.maxWidth = pageWidth - (this.margin * 2);
          this.yPosition = Math.max(80, this.margin);
          this.lineHeight = 6;
          this.currentFontSize = 12;
        }
        normalizeToAscii(text) {
          if (text == null) return '';
          return text
            .toString()
            .replace(/[\u2018\u2019]/g, "'")
            .replace(/[\u201C\u201D]/g, '"')
            .replace(/[\u2013\u2014]/g, '-')
            .replace(/[\u2022\u00B7]/g, '-')
            .replace(/[\u2026]/g, '...')
            .replace(/[\u00A0\u202F\u2009]/g, ' ')
            .replace(/[\u200B]/g, '');
        }
        softWrapLongWords(text) {
          if (!text) return '';
          const SOFT_BREAK_EVERY = 18;
          return text
            .split(/(\s+)/)
            .map(token => {
              if (/\s+/.test(token)) return token;
              if (token.length <= SOFT_BREAK_EVERY) return token;
              const parts = [];
              for (let i = 0; i < token.length; i += SOFT_BREAK_EVERY) {
                parts.push(token.slice(i, i + SOFT_BREAK_EVERY));
              }
              return parts.join('\u200b');
            })
            .join('');
        }
        isFillerString(text) {
          if (!text) return true;
          const compact = text.toString().replace(/[\s\u200b]+/g, '');
          if (compact.length < 3) return false;
          const filler = compact.match(/[-_–—.=]{3,}/g);
          if (!filler) return false;
          const fillerLen = filler.join('').length;
          return fillerLen / compact.length >= 0.7;
        }
        checkPageBreak(requiredHeight = 20) {
          if (this.yPosition + requiredHeight > this.pageHeight) {
            this.pdf.addPage();
            this.yPosition = 20;
          }
        }
        setFont(size = 12, style = 'normal', font = 'helvetica') {
          try {
            this.pdf.setFont(font, style);
            this.pdf.setFontSize(size);
            this.currentFontSize = size;
          } catch (error) {
            this.pdf.setFont('helvetica', 'normal');
            this.pdf.setFontSize(size);
          }
        }
        addText(text, indent = 0, maxWidth = null) {
          if (!text || !text.trim()) return;
          try {
            const effectiveWidth = maxWidth || (this.maxWidth - indent);
            const textStr = this.normalizeToAscii(text.toString());
            const hardLines = textStr.split(/\r?\n/);
            for (const hardLine of hardLines) {
              const wrapped = this.pdf.splitTextToSize(hardLine, effectiveWidth);
              for (let i = 0; i < wrapped.length; i++) {
                this.checkPageBreak(10);
                this.pdf.text(wrapped[i], this.margin + indent, this.yPosition);
                this.yPosition += this.lineHeight;
              }
            }
          } catch (error) {
            this.checkPageBreak(10);
            this.pdf.text(this.normalizeToAscii(text.toString()).substring(0, 100), this.margin + indent, this.yPosition);
            this.yPosition += this.lineHeight;
          }
        }
        addSpacing(multiplier = 1) {
          this.yPosition += (this.lineHeight * multiplier);
        }
        processInlineFormatting(text) {
          if (!text) return '';
          try {
            text = this.normalizeToAscii(text.toString());
            text = text.replace(/\*{2}(.*?)\*{2}/g, '$1');
            text = text.replace(/__([^_]+)__/g, '$1');
            text = text.replace(/\*([^*]+)\*/g, '$1');
            text = text.replace(/_([^_]+)_/g, '$1');
            text = text.replace(/`([^`]+)`/g, '$1');
            text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
            text = text.replace(/~~(.*?)~~/g, '$1');
            return this.softWrapLongWords(text.trim());
          } catch (error) {
            return this.softWrapLongWords(text.toString().trim());
          }
        }
        renderTable(tableLines) {
          try {
            if (!tableLines || tableLines.length < 2) return;
            const validLines = tableLines.filter(line => 
              line.trim() &&
              line.includes('|') &&
              !line.match(/^\s*\|?[\s\-:]+\|?\s*$/)
            );
            if (validLines.length === 0) return;
            const parsedRows = validLines.map((line) => {
              const t = line.trim();
              const parts = line.split('|');
              if (t.startsWith('|')) parts.shift();
              if (t.endsWith('|')) parts.pop();
              return parts.map(cell => this.processInlineFormatting(cell.trim()));
            });
            const headerCells = parsedRows[0] || [];
            let dataRows = parsedRows.slice(1);
            const isDashOnly = (text) => {
              if (!text) return true;
              const t = (text || '').toString();
              const compact = t.replace(/\s+/g, '');
              if (compact.length === 0) return true;
              const fillerMatches = compact.match(/[-_–—.]/g) || [];
              return fillerMatches.length / compact.length >= 0.7;
            };
            if (headerCells.length > 0) {
              const threshold = Math.max(2, Math.ceil(headerCells.length * 0.6));
              dataRows = dataRows.filter(cells => {
                const dashCount = cells.reduce((acc, c) => acc + (isDashOnly(c) ? 1 : 0), 0);
                if (dashCount >= threshold) return false;
                const rowJoin = (cells.join(' ') || '').replace(/\s+/g, '');
                if (rowJoin && (rowJoin.match(/[-_–—.]/g) || []).length / rowJoin.length >= 0.7) {
                  return false;
                }
                return true;
              });
            }
            const numCols = headerCells.length;
            if (numCols === 0) return;
            const availableWidth = this.maxWidth - 10;
            const weights = new Array(numCols).fill(0);
            const considerRows = [headerCells, ...dataRows];
            for (const row of considerRows) {
              for (let c = 0; c < numCols; c++) {
                const text = (row[c] || '').toString();
                weights[c] = Math.max(weights[c], Math.min(text.length, 60));
              }
            }
            const totalWeight = weights.reduce((s, w) => s + Math.max(w, 8), 0);
            const colWidths = weights.map(w => Math.max((Math.max(w, 8) / totalWeight) * availableWidth, 25));
            const cellPaddingX = 3;
            const rowMinHeight = 14;
            const drawHeader = () => {
              const headerHeights = headerCells.map((text, idx) => {
                const lines = this.pdf.splitTextToSize(text || '', colWidths[idx] - (cellPaddingX * 2));
                return Math.max(lines.length * 6 + 6, rowMinHeight);
              });
              const headerHeight = Math.max(...headerHeights);
              if (this.yPosition + headerHeight > this.pageHeight) {
                this.pdf.addPage();
                this.yPosition = this.margin;
              }
              let x = this.margin + 5;
              const y = this.yPosition;
              for (let c = 0; c < numCols; c++) {
                this.pdf.setDrawColor(200, 200, 200);
                this.pdf.setLineWidth(0.5);
                this.pdf.setFillColor(245, 245, 245);
                this.pdf.rect(x, y, colWidths[c], headerHeight, 'FD');
                this.setFont(10, 'bold');
                this.pdf.setTextColor(0, 0, 0);
                const lines = this.pdf.splitTextToSize(headerCells[c] || '', colWidths[c] - (cellPaddingX * 2));
                let ty = y + 8;
                for (const ln of lines) {
                  this.pdf.text(ln, x + cellPaddingX, ty);
                  ty += 6;
                }
                x += colWidths[c];
              }
              this.yPosition += headerHeight;
            };
            const drawDataRow = (cells) => {
              const heights = cells.map((text, idx) => {
                const lines = this.pdf.splitTextToSize(text || '', colWidths[idx] - (cellPaddingX * 2));
                return Math.max(lines.length * 6 + 6, rowMinHeight);
              });
              const rowHeight = Math.max(...heights);
              if (this.yPosition + rowHeight > this.pageHeight) {
                this.pdf.addPage();
                this.yPosition = this.margin;
                drawHeader();
              }
              let x = this.margin + 5;
              const y = this.yPosition;
              for (let c = 0; c < numCols; c++) {
                this.pdf.setDrawColor(200, 200, 200);
                this.pdf.setLineWidth(0.5);
                this.pdf.rect(x, y, colWidths[c], rowHeight, 'S');
                this.setFont(10, 'normal');
                this.pdf.setTextColor(0, 0, 0);
                const lines = this.pdf.splitTextToSize(cells[c] || '', colWidths[c] - (cellPaddingX * 2));
                let ty = y + 8;
                for (const ln of lines) {
                  if (ty > y + rowHeight - 2) break;
                  this.pdf.text(ln, x + cellPaddingX, ty);
                  ty += 6;
                }
                x += colWidths[c];
              }
              this.yPosition += rowHeight;
            };
            drawHeader();
            for (const row of dataRows) {
              const cells = Array.from({ length: numCols }, (_, i) => row[i] || '');
              drawDataRow(cells);
            }
            this.addSpacing(2);
            this.setFont(12, 'normal');
            this.pdf.setTextColor(0, 0, 0);
          } catch (error) {
            this.addText('Table content could not be rendered properly');
            this.addSpacing(1);
          }
        }
        renderList(content) {
          try {
            const lines = content.split('\n');
            for (const line of lines) {
              if (!line.trim()) continue;
              const bulletMatch = line.match(/^(\s*)[•*+-]\s+(.*)$/);
              const numberedMatch = line.match(/^(\s*)(\d+)\.\s+(.*)$/);
              if (bulletMatch) {
                const indent = bulletMatch[1].length;
                const text = this.processInlineFormatting(bulletMatch[2]);
                if (this.isFillerString(text)) continue;
                const startX = this.margin + indent * 5;
                const availableWidth = this.maxWidth - (indent * 5);
                const wrapped = this.pdf.splitTextToSize(`- ${text}`, availableWidth);
                for (let i = 0; i < wrapped.length; i++) {
                  this.checkPageBreak(10);
                  this.pdf.text(wrapped[i], startX, this.yPosition);
                  this.yPosition += this.lineHeight + 1;
                }
              } else if (numberedMatch) {
                const indent = numberedMatch[1].length;
                const num = numberedMatch[2];
                const text = this.processInlineFormatting(numberedMatch[3]);
                if (this.isFillerString(text)) continue;
                const startX = this.margin + indent * 5;
                const availableWidth = this.maxWidth - (indent * 5);
                const wrapped = this.pdf.splitTextToSize(`${num}. ${text}`, availableWidth);
                for (let i = 0; i < wrapped.length; i++) {
                  this.checkPageBreak(10);
                  this.pdf.text(wrapped[i], startX, this.yPosition);
                  this.yPosition += this.lineHeight + 1;
                }
              } else if (line.trim().startsWith('•')) {
                const text = this.processInlineFormatting(line.trim()).replace(/^•\s*/, '- ');
                if (this.isFillerString(text)) continue;
                const startX = this.margin;
                const wrapped = this.pdf.splitTextToSize(text, this.maxWidth);
                for (let i = 0; i < wrapped.length; i++) {
                  this.checkPageBreak(10);
                  this.pdf.text(wrapped[i], startX, this.yPosition);
                  this.yPosition += this.lineHeight + 1;
                }
              }
            }
            this.addSpacing(1);
          } catch (error) {
            this.addText('List content could not be rendered properly');
            this.addSpacing(1);
          }
        }
        parseMarkdown(markdown) {
          if (!markdown) return;
          try {
            const lines = markdown.split('\n');
            let i = 0;
            while (i < lines.length) {
              const line = lines[i].trim();
              if (!line) { i++; continue; }
              if (line.match(/^#{1,6}\s/)) {
                const level = (line.match(/^(#+)/) || ['', ''])[1].length;
                const text = line.replace(/^#+\s*/, '');
                this.addSpacing(level === 1 ? 2 : 1);
                if (level === 1) { this.setFont(18, 'bold'); }
                else if (level === 2) { this.setFont(16, 'bold'); }
                else if (level === 3) { this.setFont(14, 'bold'); }
                else { this.setFont(12, 'bold'); }
                this.addText(this.processInlineFormatting(text));
                this.addSpacing(0.5);
                this.setFont(12, 'normal');
                i++;
                continue;
              }
              if (line.includes('|')) {
                const tableLines = [];
                while (i < lines.length && (lines[i].includes('|') || lines[i].match(/^\s*\|?[\s\-:]+\|?\s*$/))) {
                  if (lines[i].trim()) { tableLines.push(lines[i]); }
                  i++;
                }
                this.renderTable(tableLines);
                continue;
              }
              if (line.match(/^(\s*)[•*-]\s/) || line.match(/^(\s*)\d+\.\s/)) {
                const listLines = [];
                while (i < lines.length && (lines[i].match(/^(\s*)[•*-]\s/) || lines[i].match(/^(\s*)\d+\.\s/) || lines[i].trim().startsWith('•'))) {
                  listLines.push(lines[i]);
                  i++;
                }
                this.renderList(listLines.join('\n'));
                continue;
              }
              if (line.startsWith('>')) {
                this.pdf.setTextColor(100, 100, 100);
                this.setFont(11, 'italic');
                this.addText(this.processInlineFormatting(line.substring(1).trim()), 10);
                this.pdf.setTextColor(0, 0, 0);
                this.setFont(12, 'normal');
                this.addSpacing(1);
                i++;
                continue;
              }
              if (line.match(/^[-*_]{3,}$/)) {
                this.addSpacing(0.5);
                i++;
                continue;
              }
              let paragraphLines = [line];
              i++;
              while (i < lines.length && lines[i].trim() && !lines[i].match(/^#{1,6}\s/) && !lines[i].includes('|') && !lines[i].match(/^(\s*)[•*-]\s/) && !lines[i].match(/^(\s*)\d+\.\s/) && !lines[i].startsWith('>') && !lines[i].match(/^[-*_]{3,}$/)) {
                paragraphLines.push(lines[i].trim());
                i++;
              }
              const paragraphText = paragraphLines.join('\n');
              if (this.isFillerString(paragraphText)) { this.addSpacing(0.5); continue; }
              const processed = this.softWrapLongWords(this.processInlineFormatting(paragraphText));
              this.addText(processed);
              this.addSpacing(1);
            }
          } catch (error) {
            this.addText('Content could not be parsed properly. Showing raw text:');
            this.addSpacing(1);
            this.addText(markdown.toString().substring(0, 500) + '...');
          }
        }
      }

      pdf.setFont('helvetica', 'normal');
      try {
        pdf.setFontSize(20);
        pdf.setFont('helvetica', 'bold');
        pdf.text((title || 'Document'), 20, 30);
      } catch (error) {
        pdf.setFontSize(16);
        pdf.text('Document', 20, 30);
      }

      pdf.setFontSize(11);
      pdf.setFont('helvetica', 'normal');
      pdf.setTextColor(80, 80, 80);

      let metaY = 45;
      if (meta.asset_type) { pdf.text(`Type: ${meta.asset_type}`, 20, metaY); metaY += 7; }
      if (meta.asset_category) { pdf.text(`Category: ${meta.asset_category}`, 20, metaY); metaY += 7; }
      if (meta.updated_by) { pdf.text(`Updated by: ${meta.updated_by}`, 20, metaY); metaY += 7; }
      if (meta.updated_at) {
        try { const date = new Date(meta.updated_at); pdf.text(`Last updated: ${date.toLocaleString()}`, 20, metaY); }
        catch { pdf.text(`Last updated: ${meta.updated_at}`, 20, metaY); }
        metaY += 7;
      }

      pdf.setTextColor(0, 0, 0);
      pdf.setFontSize(12);

      const parser = new MarkdownToPDF(pdf);
      parser.yPosition = Math.max(80, metaY + 10);
      parser.parseMarkdown(parser.normalizeToAscii(content || ''));

      try {
        const pageCount = pdf.internal.getNumberOfPages();
        const currentDate = new Date().toLocaleString();
        for (let pageNum = 1; pageNum <= pageCount; pageNum++) {
          pdf.setPage(pageNum);
          pdf.setFontSize(9);
          pdf.setTextColor(120, 120, 120);
          pdf.text(`Generated on ${currentDate}`, 20, 285);
          if (pageCount > 1) {
            pdf.text(`Page ${pageNum} of ${pageCount}`, 150, 285);
          }
        }
      } catch {}

      const sanitizedName = (title || 'document').toString().replace(/[^a-zA-Z0-9-_]/g, '_');
      pdf.save(`${sanitizedName}.pdf`);
    } catch (error) {
      console.error('PDF generation error:', error);
      throw new Error(`Failed to generate PDF: ${error.message}`);
    }
  },
  // Generate a PDF Blob from raw markdown/text content using backend text_to_pdf utility
  generateContentPdfBlob: async (title, content, meta = {}) => {
    try {
      const courseId = localStorage.getItem('currentCourseId');
      if (!courseId) {
        throw new Error('No course ID found');
      }

      const filename = `${title || 'asset'}.pdf`;

      // Use backend text_to_pdf endpoint
      const response = await axiosInstance.post(
        `/courses/${courseId}/assets/pdf`,
        { content, filename },
        { responseType: 'blob' }
      );

      return new Blob([response.data], { type: 'application/pdf' });
    } catch (error) {
      console.error('PDF generation error:', error);
      throw new Error(`Failed to generate PDF: ${error.message}`);
    }
  },
  // OLD FRONTEND IMPLEMENTATION - REMOVED TO USE BACKEND text_to_pdf
  generateContentPdfBlob_OLD_UNUSED: async (title, content, meta = {}) => {
    try {
      const pdf = new jsPDF();

      class MarkdownToPDF {
        constructor(pdf) {
          this.pdf = pdf;
          this.margin = 20;
          const pageWidth = this.pdf.internal.pageSize.getWidth();
          const pageHeight = this.pdf.internal.pageSize.getHeight();
          this.pageWidth = pageWidth;
          this.pageHeight = pageHeight - 20;
          this.maxWidth = pageWidth - (this.margin * 2);
          this.yPosition = Math.max(80, this.margin);
          this.lineHeight = 6;
          this.currentFontSize = 12;
        }
        normalizeToAscii(text) {
          if (text == null) return '';
          return text
            .toString()
            .replace(/[\u2018\u2019]/g, "'")
            .replace(/[\u201C\u201D]/g, '"')
            .replace(/[\u2013\u2014]/g, '-')
            .replace(/[\u2022\u00B7]/g, '-')
            .replace(/[\u2026]/g, '...')
            .replace(/[\u00A0\u202F\u2009]/g, ' ')
            .replace(/[\u200B]/g, '');
        }
        softWrapLongWords(text) {
          if (!text) return '';
          const SOFT_BREAK_EVERY = 18;
          return text
            .split(/(\s+)/)
            .map(token => {
              if (/\s+/.test(token)) return token;
              if (token.length <= SOFT_BREAK_EVERY) return token;
              const parts = [];
              for (let i = 0; i < token.length; i += SOFT_BREAK_EVERY) {
                parts.push(token.slice(i, i + SOFT_BREAK_EVERY));
              }
              return parts.join('\u200b');
            })
            .join('');
        }
        isFillerString(text) {
          if (!text) return true;
          const compact = text.toString().replace(/[\s\u200b]+/g, '');
          if (compact.length < 3) return false;
          const filler = compact.match(/[-_–—.=]{3,}/g);
          if (!filler) return false;
          const fillerLen = filler.join('').length;
          return fillerLen / compact.length >= 0.7;
        }
        checkPageBreak(requiredHeight = 20) {
          if (this.yPosition + requiredHeight > this.pageHeight) {
            this.pdf.addPage();
            this.yPosition = 20;
          }
        }
        setFont(size = 12, style = 'normal', font = 'helvetica') {
          try {
            this.pdf.setFont(font, style);
            this.pdf.setFontSize(size);
            this.currentFontSize = size;
          } catch (error) {
            this.pdf.setFont('helvetica', 'normal');
            this.pdf.setFontSize(size);
          }
        }
        addText(text, indent = 0, maxWidth = null) {
          if (!text || !text.trim()) return;
          try {
            const effectiveWidth = maxWidth || (this.maxWidth - indent);
            const textStr = this.normalizeToAscii(text.toString());
            const hardLines = textStr.split(/\r?\n/);
            for (const hardLine of hardLines) {
              const wrapped = this.pdf.splitTextToSize(hardLine, effectiveWidth);
              for (let i = 0; i < wrapped.length; i++) {
                this.checkPageBreak(10);
                this.pdf.text(wrapped[i], this.margin + indent, this.yPosition);
                this.yPosition += this.lineHeight;
              }
            }
          } catch (error) {
            this.checkPageBreak(10);
            this.pdf.text(this.normalizeToAscii(text.toString()).substring(0, 100), this.margin + indent, this.yPosition);
            this.yPosition += this.lineHeight;
          }
        }
        addSpacing(multiplier = 1) {
          this.yPosition += (this.lineHeight * multiplier);
        }
        processInlineFormatting(text) {
          if (!text) return '';
          try {
            text = this.normalizeToAscii(text.toString());
            text = text.replace(/\*{2}(.*?)\*{2}/g, '$1');
            text = text.replace(/__([^_]+)__/g, '$1');
            text = text.replace(/\*([^*]+)\*/g, '$1');
            text = text.replace(/_([^_]+)_/g, '$1');
            text = text.replace(/`([^`]+)`/g, '$1');
            text = text.replace(/\[([^\]]+)\]\([^)]+\)/g, '$1');
            text = text.replace(/~~(.*?)~~/g, '$1');
            return this.softWrapLongWords(text.trim());
          } catch (error) {
            return this.softWrapLongWords(text.toString().trim());
          }
        }
        renderTable(tableLines) {
          try {
            if (!tableLines || tableLines.length < 2) return;
            const validLines = tableLines.filter(line => 
              line.trim() &&
              line.includes('|') &&
              !line.match(/^\s*\|?[\s\-:]+\|?\s*$/)
            );
            if (validLines.length === 0) return;
            const parsedRows = validLines.map((line) => {
              const t = line.trim();
              const parts = line.split('|');
              if (t.startsWith('|')) parts.shift();
              if (t.endsWith('|')) parts.pop();
              return parts.map(cell => this.processInlineFormatting(cell.trim()));
            });
            const headerCells = parsedRows[0] || [];
            let dataRows = parsedRows.slice(1);
            const isDashOnly = (text) => {
              if (!text) return true;
              const t = (text || '').toString();
              const compact = t.replace(/\s+/g, '');
              if (compact.length === 0) return true;
              const fillerMatches = compact.match(/[-_–—.]/g) || [];
              return fillerMatches.length / compact.length >= 0.7;
            };
            if (headerCells.length > 0) {
              const threshold = Math.max(2, Math.ceil(headerCells.length * 0.6));
              dataRows = dataRows.filter(cells => {
                const dashCount = cells.reduce((acc, c) => acc + (isDashOnly(c) ? 1 : 0), 0);
                if (dashCount >= threshold) return false;
                const rowJoin = (cells.join(' ') || '').replace(/\s+/g, '');
                if (rowJoin && (rowJoin.match(/[-_–—.]/g) || []).length / rowJoin.length >= 0.7) {
                  return false;
                }
                return true;
              });
            }
            const numCols = headerCells.length;
            if (numCols === 0) return;
            const availableWidth = this.maxWidth - 10;
            const weights = new Array(numCols).fill(0);
            const considerRows = [headerCells, ...dataRows];
            for (const row of considerRows) {
              for (let c = 0; c < numCols; c++) {
                const text = (row[c] || '').toString();
                weights[c] = Math.max(weights[c], Math.min(text.length, 60));
              }
            }
            const totalWeight = weights.reduce((s, w) => s + Math.max(w, 8), 0);
            const colWidths = weights.map(w => Math.max((Math.max(w, 8) / totalWeight) * availableWidth, 25));
            const cellPaddingX = 3;
            const rowMinHeight = 14;
            const drawHeader = () => {
              const headerHeights = headerCells.map((text, idx) => {
                const lines = this.pdf.splitTextToSize(text || '', colWidths[idx] - (cellPaddingX * 2));
                return Math.max(lines.length * 6 + 6, rowMinHeight);
              });
              const headerHeight = Math.max(...headerHeights);
              if (this.yPosition + headerHeight > this.pageHeight) {
                this.pdf.addPage();
                this.yPosition = this.margin;
              }
              let x = this.margin + 5;
              const y = this.yPosition;
              for (let c = 0; c < numCols; c++) {
                this.pdf.setDrawColor(200, 200, 200);
                this.pdf.setLineWidth(0.5);
                this.pdf.setFillColor(245, 245, 245);
                this.pdf.rect(x, y, colWidths[c], headerHeight, 'FD');
                this.setFont(10, 'bold');
                this.pdf.setTextColor(0, 0, 0);
                const lines = this.pdf.splitTextToSize(headerCells[c] || '', colWidths[c] - (cellPaddingX * 2));
                let ty = y + 8;
                for (const ln of lines) {
                  this.pdf.text(ln, x + cellPaddingX, ty);
                  ty += 6;
                }
                x += colWidths[c];
              }
              this.yPosition += headerHeight;
            };
            const drawDataRow = (cells) => {
              const heights = cells.map((text, idx) => {
                const lines = this.pdf.splitTextToSize(text || '', colWidths[idx] - (cellPaddingX * 2));
                return Math.max(lines.length * 6 + 6, rowMinHeight);
              });
              const rowHeight = Math.max(...heights);
              if (this.yPosition + rowHeight > this.pageHeight) {
                this.pdf.addPage();
                this.yPosition = this.margin;
                drawHeader();
              }
              let x = this.margin + 5;
              const y = this.yPosition;
              for (let c = 0; c < numCols; c++) {
                this.pdf.setDrawColor(200, 200, 200);
                this.pdf.setLineWidth(0.5);
                this.pdf.rect(x, y, colWidths[c], rowHeight, 'S');
                this.setFont(10, 'normal');
                this.pdf.setTextColor(0, 0, 0);
                const lines = this.pdf.splitTextToSize(cells[c] || '', colWidths[c] - (cellPaddingX * 2));
                let ty = y + 8;
                for (const ln of lines) {
                  if (ty > y + rowHeight - 2) break;
                  this.pdf.text(ln, x + cellPaddingX, ty);
                  ty += 6;
                }
                x += colWidths[c];
              }
              this.yPosition += rowHeight;
            };
            drawHeader();
            for (const row of dataRows) {
              const cells = Array.from({ length: numCols }, (_, i) => row[i] || '');
              drawDataRow(cells);
            }
            this.addSpacing(2);
            this.setFont(12, 'normal');
            this.pdf.setTextColor(0, 0, 0);
          } catch (error) {
            this.addText('Table content could not be rendered properly');
            this.addSpacing(1);
          }
        }
        renderList(content) {
          try {
            const lines = content.split('\n');
            for (const line of lines) {
              if (!line.trim()) continue;
              const bulletMatch = line.match(/^(\s*)[•*+-]\s+(.*)$/);
              const numberedMatch = line.match(/^(\s*)(\d+)\.\s+(.*)$/);
              if (bulletMatch) {
                const indent = bulletMatch[1].length;
                const text = this.processInlineFormatting(bulletMatch[2]);
                if (this.isFillerString(text)) continue;
                const startX = this.margin + indent * 5;
                const availableWidth = this.maxWidth - (indent * 5);
                const wrapped = this.pdf.splitTextToSize(`- ${text}`, availableWidth);
                for (let i = 0; i < wrapped.length; i++) {
                  this.checkPageBreak(10);
                  this.pdf.text(wrapped[i], startX, this.yPosition);
                  this.yPosition += this.lineHeight + 1;
                }
              } else if (numberedMatch) {
                const indent = numberedMatch[1].length;
                const num = numberedMatch[2];
                const text = this.processInlineFormatting(numberedMatch[3]);
                if (this.isFillerString(text)) continue;
                const startX = this.margin + indent * 5;
                const availableWidth = this.maxWidth - (indent * 5);
                const wrapped = this.pdf.splitTextToSize(`${num}. ${text}`, availableWidth);
                for (let i = 0; i < wrapped.length; i++) {
                  this.checkPageBreak(10);
                  this.pdf.text(wrapped[i], startX, this.yPosition);
                  this.yPosition += this.lineHeight + 1;
                }
              } else if (line.trim().startsWith('•')) {
                const text = this.processInlineFormatting(line.trim()).replace(/^•\s*/, '- ');
                if (this.isFillerString(text)) continue;
                const startX = this.margin;
                const wrapped = this.pdf.splitTextToSize(text, this.maxWidth);
                for (let i = 0; i < wrapped.length; i++) {
                  this.checkPageBreak(10);
                  this.pdf.text(wrapped[i], startX, this.yPosition);
                  this.yPosition += this.lineHeight + 1;
                }
              }
            }
            this.addSpacing(1);
          } catch (error) {
            this.addText('List content could not be rendered properly');
            this.addSpacing(1);
          }
        }
        parseMarkdown(markdown) {
          if (!markdown) return;
          try {
            const lines = markdown.split('\n');
            let i = 0;
            while (i < lines.length) {
              const line = lines[i].trim();
              if (!line) { i++; continue; }
              if (line.match(/^#{1,6}\s/)) {
                const level = (line.match(/^(#+)/) || ['', ''])[1].length;
                const text = line.replace(/^#+\s*/, '');
                this.addSpacing(level === 1 ? 2 : 1);
                if (level === 1) { this.setFont(18, 'bold'); }
                else if (level === 2) { this.setFont(16, 'bold'); }
                else if (level === 3) { this.setFont(14, 'bold'); }
                else { this.setFont(12, 'bold'); }
                this.addText(this.processInlineFormatting(text));
                this.addSpacing(0.5);
                this.setFont(12, 'normal');
                i++;
                continue;
              }
              if (line.includes('|')) {
                const tableLines = [];
                while (i < lines.length && (lines[i].includes('|') || lines[i].match(/^\s*\|?[\s\-:]+\|?\s*$/))) {
                  if (lines[i].trim()) { tableLines.push(lines[i]); }
                  i++;
                }
                this.renderTable(tableLines);
                continue;
              }
              if (line.match(/^(\s*)[•*-]\s/) || line.match(/^(\s*)\d+\.\s/)) {
                const listLines = [];
                while (i < lines.length && (lines[i].match(/^(\s*)[•*-]\s/) || lines[i].match(/^(\s*)\d+\.\s/) || lines[i].trim().startsWith('•'))) {
                  listLines.push(lines[i]);
                  i++;
                }
                this.renderList(listLines.join('\n'));
                continue;
              }
              if (line.startsWith('>')) {
                this.pdf.setTextColor(100, 100, 100);
                this.setFont(11, 'italic');
                this.addText(this.processInlineFormatting(line.substring(1).trim()), 10);
                this.pdf.setTextColor(0, 0, 0);
                this.setFont(12, 'normal');
                this.addSpacing(1);
                i++;
                continue;
              }
              if (line.match(/^[-*_]{3,}$/)) {
                this.addSpacing(0.5);
                i++;
                continue;
              }
              let paragraphLines = [line];
              i++;
              while (i < lines.length && lines[i].trim() && !lines[i].match(/^#{1,6}\s/) && !lines[i].includes('|') && !lines[i].match(/^(\s*)[•*-]\s/) && !lines[i].match(/^(\s*)\d+\.\s/) && !lines[i].startsWith('>') && !lines[i].match(/^[-*_]{3,}$/)) {
                paragraphLines.push(lines[i].trim());
                i++;
              }
              const paragraphText = paragraphLines.join('\n');
              if (this.isFillerString(paragraphText)) { this.addSpacing(0.5); continue; }
              const processed = this.softWrapLongWords(this.processInlineFormatting(paragraphText));
              this.addText(processed);
              this.addSpacing(1);
            }
          } catch (error) {
            this.addText('Content could not be parsed properly. Showing raw text:');
            this.addSpacing(1);
            this.addText(markdown.toString().substring(0, 500) + '...');
          }
        }
      }

      pdf.setFont('helvetica', 'normal');
      try {
        pdf.setFontSize(20);
        pdf.setFont('helvetica', 'bold');
        pdf.text((title || 'Document'), 20, 30);
      } catch (error) {
        pdf.setFontSize(16);
        pdf.text('Document', 20, 30);
      }

      pdf.setFontSize(11);
      pdf.setFont('helvetica', 'normal');
      pdf.setTextColor(80, 80, 80);

      let metaY = 45;
      if (meta.asset_type) { pdf.text(`Type: ${meta.asset_type}`, 20, metaY); metaY += 7; }
      if (meta.asset_category) { pdf.text(`Category: ${meta.asset_category}`, 20, metaY); metaY += 7; }
      if (meta.updated_by) { pdf.text(`Updated by: ${meta.updated_by}`, 20, metaY); metaY += 7; }
      if (meta.updated_at) {
        try { const date = new Date(meta.updated_at); pdf.text(`Last updated: ${date.toLocaleString()}`, 20, metaY); }
        catch { pdf.text(`Last updated: ${meta.updated_at}`, 20, metaY); }
        metaY += 7;
      }

      pdf.setTextColor(0, 0, 0);
      pdf.setFontSize(12);

      const parser = new MarkdownToPDF(pdf);
      parser.yPosition = Math.max(80, metaY + 10);
      parser.parseMarkdown(parser.normalizeToAscii(content || ''));

      try {
        const pageCount = pdf.internal.getNumberOfPages();
        const currentDate = new Date().toLocaleString();
        for (let pageNum = 1; pageNum <= pageCount; pageNum++) {
          pdf.setPage(pageNum);
          pdf.setFontSize(9);
          pdf.setTextColor(120, 120, 120);
          pdf.text(`Generated on ${currentDate}`, 20, 285);
          if (pageCount > 1) {
            pdf.text(`Page ${pageNum} of ${pageCount}`, 150, 285);
          }
        }
      } catch {}

      const blob = pdf.output('blob');
      return blob;
    } catch (error) {
      console.error('PDF generation error:', error);
      throw new Error(`Failed to generate PDF: ${error.message}`);
    }
  },
  // Generate image for an asset type
  generateImageAsset: async (courseId, assetTypeName) => {
    try {
      const res = await axiosInstance.post(
        `/courses/${courseId}/assets/image`,
        {},
        {
          params: { asset_type_name: assetTypeName }
        }
      );
      return res.data; // expects { image_url }
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Delete asset
  deleteAsset: async (courseId, assetName) => {
    try {
      const res = await axiosInstance.delete(`/courses/${courseId}/assets/${assetName}`);
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  },

  // Save asset as resource
  saveAssetAsResource: async (courseId, assetName, content) => {
    try {
      const res = await axiosInstance.post(`/courses/${courseId}/assets/${assetName}/save-as-resource`, 
        { 
          content: content,
          asset_name: assetName
        }
      );
      return res.data;
    } catch (error) {
      handleAxiosError(error);
    }
  }
}; 