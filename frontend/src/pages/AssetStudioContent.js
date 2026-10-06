import React, { memo, useEffect, useRef, useState } from "react";
import { useLocation, useParams } from "react-router-dom";
import AssetStudioLayout from "../layouts/AssetStudioLayout";
import KnowledgeBase from "../components/KnowledgBase";
import { FaDownload, FaFolderPlus, FaSave } from "react-icons/fa";
import { getAllResources, extractResourceImages, deleteResource as deleteResourceApi } from "../services/resources";
import { assetService } from "../services/asset";
import { resolveNameConflict, getAllResourceNames } from "../utils/nameConflictHandler";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkBreaks from "remark-breaks";
import AddResourceModal from '../components/AddReferencesModal';
import DownloadButton from '../components/DownloadButton';
import { latexToText } from '../utils/latexToText';
import { API_BASE } from '../utils/axiosConfig';
import { isSprintStructure, sprintStructureComponents } from '../utils/sprintStructure';

// Resolve an image src from the AI response to a renderable URL.
// Internal knowledge-base images (e.g. /courses/{id}/images/{id}) are fetched
// from the backend via the authenticated axios base URL and converted to an
// object URL so the browser can display them without CORS / auth issues.
function useResolvedImageSrc(src) {
  const [resolvedSrc, setResolvedSrc] = useState(src);
  useEffect(() => {
    if (!src) return;
    // Only rewrite internal /courses/.../images/... paths
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

// Wrapper component so hooks can be used inside the ReactMarkdown img renderer
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
      (match, p1, offset) => (offset === 0 ? match : `\n\n${p1.trimStart()}`)
    );

    const lines = cleaned.split(/\n+/).map(l => l.trim()).filter(Boolean);
    if (lines.length <= 1) {
      // Keep the edge spaces: markdown splits "to **bold** and" into separate text
      // nodes around the bold, and trimming them glues the words together.
      return cleaned.replace(/\n+/g, " ");
    }
    return lines.map((line, idx) => (
      <div
        key={idx}
        style={{
          marginTop: idx > 0 ? "10px" : "0",
          lineHeight: "1.6"
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

const optionTitles = {
  "course-outcomes": "Course Outcomes",
  "modules": "Modules",
  "modules-and-topics": "Modules",
  "lecture": "Lecture",
  "course-notes": "Course Notes",
  "concept-plan": "Concept Plan",
  "brainstorm": "Brainstorm",
  "quiz": "Quiz",
  "assignment": "Assignment",
  "viva": "Viva",
  "sprint-plan": "Sprint Plan",
  "sprint-structure": "Sprint Structure",
  "sprint-plan-doc": "Sprint Structure"
};

const MARK_SCHEME_FIELD_PATTERN = '(?:questionnumber|question|answertemplate|markingscheme)';

const normalizeEscapes = (text = "") =>
  typeof text === "string"
    ? text.replace(/\\r\\n/g, "\n").replace(/\\n/g, "\n").replace(/\\t/g, "    ")
    : text;

const formatMarkSchemeResponse = (rawText = "") => {
  if (!rawText || typeof rawText !== "string") return rawText;
  const normalized = normalizeEscapes(rawText).replace(/\r\n/g, "\n").trim();
  if (!normalized.toLowerCase().includes("questionnumber")) return rawText;

  const sections = normalized.match(/questionnumber\s*:[\s\S]*?(?=\nquestionnumber\s*:|$)/gi);
  if (!sections) return rawText;

  const extractField = (section, field) => {
    const regex = new RegExp(`${field}\\s*:\\s*([\\s\\S]*?)(?=\\n${MARK_SCHEME_FIELD_PATTERN}\\s*:|$)`, "i");
    const match = section.match(regex);
    return match ? match[1].trim() : "";
  };

  const toBullets = (text) => {
    if (!text) return "";
    const lines = text.split(/\n+/).map(line => line.trim()).filter(Boolean);
    if (!lines.length) return text.trim();
    return lines.map(line => {
      const cleaned = line.replace(/^[-*•\d)(]+\s*/, "").trim();
      return cleaned ? `- ${cleaned}` : "";
    }).filter(Boolean).join("\n");
  };

  const formattedSections = sections.map(section => {
    const number = normalizeEscapes(extractField(section, "questionnumber"));
    const question = normalizeEscapes(extractField(section, "question"));
    const answer = normalizeEscapes(extractField(section, "answertemplate"));
    const marking = normalizeEscapes(extractField(section, "markingscheme"));

    if (!number && !question && !answer && !marking) {
      return section.trim();
    }

    const answerBlock = toBullets(answer);
    const markingLines = marking
      ? marking.split(/\n+/).map(line => line.trim()).filter(Boolean)
      : [];

    let schemeHeading = "";
    if (markingLines.length && /^marking\s*scheme/i.test(markingLines[0])) {
      schemeHeading = markingLines.shift();
    }

    const markingBlock = markingLines
      .map(line => {
        const cleaned = line.replace(/^[-*•]+\s*/, "").trim();
        return cleaned ? `- ${cleaned}` : "";
      })
      .filter(Boolean)
      .join("\n");

    const parts = [];
    if (number) {
      parts.push(`### Question ${number.trim()}`);
    }
    if (question) {
      parts.push(`**Question**  \n${question.trim().replace(/\n/g, "  \n")}`);
    }
    if (answerBlock) {
      parts.push(`**Answer Template**\n${answerBlock}`);
    }
    if (markingBlock) {
      const heading = schemeHeading || "Marking Scheme";
      parts.push(`**${heading}**\n${markingBlock}`);
    }

    return parts.join("\n\n");
  });

  return formattedSections.join("\n\n---\n\n");
};

// Type scale for assistant content. Generated assets are long-form reading
// material, so the body text is set a notch larger with generous leading and the
// headings carry real contrast against it.
const CHAT_TEXT = "16px";
const CHAT_LEADING = "1.7";
const TEXT_COLOR = "#1f2937";

const headingStyle = (fontSize, marginTop) => ({
  fontSize,
  fontWeight: 600,
  lineHeight: 1.35,
  margin: `${marginTop}px 0 8px`,
  color: "#111827"
});

// Markdown renderers for assistant messages. Defined once at module scope so the
// same styling is used for completed messages and for the live streaming preview.
const markdownComponents = {
  h1: ({ children }) => <h1 style={headingStyle("23px", 24)}>{children}</h1>,
  h2: ({ children }) => <h2 style={headingStyle("20px", 22)}>{children}</h2>,
  h3: ({ children }) => <h3 style={headingStyle("17px", 18)}>{children}</h3>,
  p: ({ children }) => <div style={{ margin: "10px 0", color: TEXT_COLOR, lineHeight: CHAT_LEADING }}>{renderFormattedContent(children)}</div>,
  li: ({ children, ordered }) => <li style={{ margin: ordered ? "10px 0" : "6px 0", paddingLeft: "2px", color: TEXT_COLOR, lineHeight: CHAT_LEADING }}>{children}</li>,
  ul: ({ children }) => <ul style={{ margin: "10px 0", paddingLeft: "24px", color: TEXT_COLOR }}>{children}</ul>,
  ol: ({ children }) => <ol style={{ margin: "10px 0", paddingLeft: "24px", color: TEXT_COLOR }}>{children}</ol>,
  strong: ({ children }) => <strong style={{ fontWeight: 600, color: "#111827" }}>{children}</strong>,
  em: ({ children }) => <em style={{ fontStyle: "italic", color: TEXT_COLOR }}>{children}</em>,
  code: ({ children }) => <code style={{ backgroundColor: "#f1f5f9", padding: "2px 5px", borderRadius: "4px", fontFamily: "monospace", fontSize: "14px", color: "#0f172a" }}>{children}</code>,
  pre: ({ children }) => <pre style={{ backgroundColor: "#f1f5f9", padding: "12px", borderRadius: "6px", overflow: "auto", margin: "12px 0", fontSize: "14px", lineHeight: "1.55", color: "#0f172a" }}>{children}</pre>,
  blockquote: ({ children }) => <blockquote style={{ borderLeft: "3px solid #cbd5e1", paddingLeft: "14px", margin: "12px 0", color: "#475569", lineHeight: CHAT_LEADING }}>{children}</blockquote>,
  table: ({ children }) => (
    <div style={{ overflowX: "auto", margin: "14px 0" }}>
      <table style={{ borderCollapse: "collapse", width: "100%", border: "1px solid #ddd", tableLayout: "fixed", fontSize: "14px" }}>{children}</table>
    </div>
  ),
  thead: ({ children }) => <thead style={{ backgroundColor: "#f5f5f5" }}>{children}</thead>,
  tbody: ({ children }) => <tbody>{children}</tbody>,
  tr: ({ children }) => <tr style={{ borderBottom: "1px solid #ddd" }}>{children}</tr>,
  th: ({ children }) => <th style={{ padding: "10px 12px", textAlign: "left", border: "1px solid #ddd", fontSize: "14px", fontWeight: 600, backgroundColor: "#f5f5f5", verticalAlign: "top", wordWrap: "break-word", lineHeight: "1.5" }}>{renderFormattedContent(children)}</th>,
  td: ({ children }) => <td style={{ padding: "10px 12px", textAlign: "left", border: "1px solid #ddd", fontSize: "14px", verticalAlign: "top", wordWrap: "break-word", lineHeight: "1.6" }}>{renderFormattedContent(children)}</td>,
  a: ({ href, children }) => <a href={href} target="_blank" rel="noopener noreferrer" style={{ color: "#2563eb", textDecoration: "underline" }}>{children}</a>,
  img: ({ src, alt }) => <ResolvedImage src={src} alt={alt} style={{ maxWidth: "100%", height: "auto", display: "block", margin: "12px auto", borderRadius: "8px", border: "1px solid #eee" }} />
};

// Sprint Structure renders its timetable colour-coded by activity type.
const sprintMarkdownComponents = { ...markdownComponents, ...sprintStructureComponents };

const REMARK_PLUGINS = [remarkGfm, remarkBreaks];

// Memoized: the page re-renders every reveal frame while streaming, and re-parsing
// every earlier answer each time is what made long chats stutter.
const BotMarkdown = memo(function BotMarkdown({ text, components = markdownComponents, className }) {
  return (
    <div className={className} style={{ fontSize: CHAT_TEXT, lineHeight: CHAT_LEADING, color: TEXT_COLOR }}>
      <ReactMarkdown remarkPlugins={REMARK_PLUGINS} components={components}>
        {latexToText(text)}
      </ReactMarkdown>
    </div>
  );
});

// Streaming reveal: the visible text eases toward whatever the backend has sent so
// far (exponential approach with time constant REVEAL_TAU_S) plus a floor speed so
// the tail never crawls. The speed therefore changes continuously instead of jumping
// with each 500ms poll.
const REVEAL_TAU_S = 0.35;
const REVEAL_MIN_CPS = 120;
// Re-parsing the markdown every frame is wasted work on long answers: ~30fps is smooth.
// Past REVEAL_LONG_CHARS each parse gets expensive, so commit less often (~10fps).
const REVEAL_COMMIT_MS = 33;
const REVEAL_LONG_CHARS = 8000;
const REVEAL_LONG_COMMIT_MS = 100;

function useSmoothReveal(text, active) {
  const [shownLength, setShownLength] = useState(0);
  const shownRef = useRef(0);
  const textRef = useRef(text);
  textRef.current = text;

  useEffect(() => {
    if (!active) {
      shownRef.current = 0;
      setShownLength(0);
      return;
    }
    // requestAnimationFrame + elapsed time: a throttled background tab simply
    // catches up when it becomes visible again.
    let frame;
    let last = performance.now();
    let lastCommit = 0;
    let carry = 0;
    const tick = (now) => {
      const dt = (now - last) / 1000;
      last = now;
      const target = textRef.current.length;
      let shown = Math.min(shownRef.current, target);
      const backlog = target - shown;
      if (backlog > 0) {
        carry += backlog * (1 - Math.exp(-dt / REVEAL_TAU_S)) + REVEAL_MIN_CPS * dt;
        const step = Math.floor(carry);
        carry -= step;
        shown = Math.min(target, shown + step);
      } else {
        carry = 0;
      }
      const commitMs = target > REVEAL_LONG_CHARS ? REVEAL_LONG_COMMIT_MS : REVEAL_COMMIT_MS;
      if (shown !== shownRef.current && (shown === target || now - lastCommit >= commitMs)) {
        shownRef.current = shown;
        lastCommit = now;
        setShownLength(shown);
      }
      frame = requestAnimationFrame(tick);
    };
    frame = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(frame);
  }, [active]);

  return text ? text.slice(0, shownLength) : "";
}

// scrollTop at which `node` sits at the top of the scroll container `el`.
function scrollTopFor(el, node) {
  const paddingTop = parseFloat(getComputedStyle(el).paddingTop) || 0;
  return el.scrollTop + node.getBoundingClientRect().top - el.getBoundingClientRect().top - paddingTop;
}

// Longest the final message waits for the preview to finish revealing its tail.
const SETTLE_TIMEOUT_MS = 1500;

// Collapsed height of the composer: one line of 16px/1.5 text plus 9px padding.
const COMPOSER_ROW_HEIGHT = 42;

// While streaming, image links are still raw (`image_ref:<id>`) and markdown can be
// cut mid-token: drop images so no broken picture flashes before the final message.
const stripStreamingImages = (text = "") => text.replace(/!\[[^\]]*\]\([^)]*\)?/g, "");

export default function AssetStudioContent() {
  const params = useParams();
  const option = params.feature;
  const location = useLocation();
  const scrollRef = useRef(null);
  // Top of the newest answer: the live preview while streaming, then the final message.
  const responseStartRef = useRef(null);
  const title = optionTitles[option] || option;
  const botComponents = isSprintStructure(option) ? sprintMarkdownComponents : markdownComponents;

  // ✅ Pre-select only those passed from Dashboard
  const selectedFiles = location.state?.selectedFiles || [];
  const initialSelectedIds = selectedFiles.map(file => file.id || file.fileName || file.name);
  const [selectedIds, setSelectedIds] = useState(initialSelectedIds);

  const [chatMessages, setChatMessages] = useState([]);
  const [streamingText, setStreamingText] = useState("");
  const [inputMessage, setInputMessage] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [resources, setResources] = useState([]);
  const [resourcesLoading, setResourcesLoading] = useState(true);
  const [isUploadingResources, setIsUploadingResources] = useState(false);
  const [lastResponseId, setLastResponseId] = useState(null);
  const [showSaveModal, setShowSaveModal] = useState(false);
  const [saveModalMessage, setSaveModalMessage] = useState("");
  const [assetName, setAssetName] = useState("");
  const [showAddResourceModal, setShowAddResourceModal] = useState(false);
  const [isSavingAsset, setIsSavingAsset] = useState(false);
  const [isSavingResource, setIsSavingResource] = useState(false);
  const [showSaveResourceModal, setShowSaveResourceModal] = useState(false);
  const [resourceFileName, setResourceFileName] = useState("");
  const [resourceSaveMessage, setResourceSaveMessage] = useState("");
  const hasInitializedRef = useRef(false);
  const isSendingRef = useRef(false);
  const isSavingResourceRef = useRef(false);
  const textareaRef = useRef(null);

  // A generation is either running or about to start: with files selected and no
  // message yet, the initial asset is on its way, so show the busy state straight
  // away instead of flashing the "nothing selected" hint for one frame.
  const isBusy = isLoading || (chatMessages.length === 0 && selectedIds.length > 0);
  const revealedStream = useSmoothReveal(streamingText, isBusy);

  // Set once the user scrolls the transcript themselves during a generation: from
  // then on the view is theirs and nothing auto-scrolls until the next message.
  const userScrolledRef = useRef(false);
  const markUserScrolled = () => {
    if (isBusy) userScrolledRef.current = true;
  };

  // While an answer streams, glide down with the new text until the START of the
  // answer reaches the top of the transcript, then stop there so it is read from
  // the top. Eased per frame, so line wraps don't make the view jump.
  useEffect(() => {
    if (!isBusy) return;
    let frame;
    const follow = () => {
      const el = scrollRef.current;
      const start = responseStartRef.current;
      if (el && start && !userScrolledRef.current) {
        const target = Math.min(scrollTopFor(el, start), el.scrollHeight - el.clientHeight);
        const diff = target - el.scrollTop;
        if (diff > 1) el.scrollTop += Math.max(1, diff * 0.15);
      }
      frame = requestAnimationFrame(follow);
    };
    frame = requestAnimationFrame(follow);
    return () => cancelAnimationFrame(frame);
  }, [isBusy]);

  // A message just sent: show it (and the typing indicator) at the bottom. A final
  // answer: keep its start at the top, where the stream left it.
  useEffect(() => {
    const el = scrollRef.current;
    const last = chatMessages[chatMessages.length - 1];
    if (!el || !last) return;
    if (last.type === "user") {
      el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    } else if (responseStartRef.current && !userScrolledRef.current) {
      el.scrollTo({ top: scrollTopFor(el, responseStartRef.current), behavior: "smooth" });
    }
  }, [chatMessages]);

  // Before the final message replaces the live preview, let the preview finish
  // revealing the last few words so the end of the answer doesn't pop in at once.
  const streamingTextRef = useRef("");
  streamingTextRef.current = streamingText;
  const settleRef = useRef(null);
  const settleStream = (finalText) => new Promise(resolve => {
    if (!streamingTextRef.current) return resolve(); // nothing was streamed
    const done = () => {
      clearTimeout(timer);
      settleRef.current = null;
      resolve();
    };
    const timer = setTimeout(done, SETTLE_TIMEOUT_MS);
    settleRef.current = done;
    setStreamingText(finalText);
  });
  useEffect(() => {
    if (settleRef.current && streamingText && revealedStream.length >= streamingText.length) {
      settleRef.current();
    }
  }, [revealedStream, streamingText]);

  useEffect(() => {
    const fetchResources = async () => {
      try {
        setResourcesLoading(true);
        const courseId = localStorage.getItem('currentCourseId');
        if (!courseId) {
          console.error('No current course ID found');
          setResources([]);
          return;
        }

        const resourcesData = await getAllResources(courseId);
        setResources(resourcesData.resources);
      } catch (error) {
        console.error("Error fetching resources:", error);
        setResources([]);
      } finally {
        setResourcesLoading(false);
      }
    };

    fetchResources();
  }, []);

  // Create initial AI message only after resources have finished loading
  useEffect(() => {
    const createInitialMessage = async () => {
      try {
        const courseId = localStorage.getItem('currentCourseId');
        if (!courseId) {
          console.error('No course ID found');
          return;
        }

        // If no files were selected, do not create an initial message
        if (!selectedIds || selectedIds.length === 0) {
          return;
        }

        setIsLoading(true);

        // Create asset chat using ONLY selected resources (no fallback)
        const resolveId = (r) => r.id || r.resourceName || r.fileName;
        const chosen = resources.filter(r => selectedIds.includes(resolveId(r)));
        const fileNames = chosen.map(file => file.resourceName || file.fileName || resolveId(file));

        // Debug logging
        console.log('Selected IDs:', selectedIds);
        console.log('Available resources:', resources.map(r => ({ id: resolveId(r), name: r.resourceName || r.fileName })));
        console.log('Chosen files:', chosen);
        console.log('File names being sent:', fileNames);

        const taskResponse = await assetService.createAssetChat(courseId, option, fileNames);
        const taskId = taskResponse?.task_id;

        if (taskId) {
          // Poll for task completion (throws if the task failed on the backend)
          const result = await assetService.pollTaskUntilComplete(taskId, 1200, 500, setStreamingText);
          if (result && result.response) {
            const normalizedResponse = normalizeEscapes(result.response);
            const formattedResponse = option === 'mark-scheme'
              ? formatMarkSchemeResponse(normalizedResponse)
              : normalizedResponse;
            await settleStream(formattedResponse);
            setChatMessages(prev => [...prev, { type: "bot", text: formattedResponse }]);
            setLastResponseId(result.response_id);
          }
        }
      } catch (error) {
        console.error("Error creating initial message:", error);
        setChatMessages(prev => [...prev, {
          type: "bot",
          text: `⚠️ Generation failed: ${error.message || 'Unknown error'}. Please try again.`
        }]);
      } finally {
        setStreamingText("");
        setIsLoading(false);
      }
    };

    // Guard against double-invocation and ensure resources have been fetched first
    // Only run once when resources finish loading, ignore subsequent resource updates
    if (!hasInitializedRef.current && !resourcesLoading && chatMessages.length === 0 && resources.length > 0) {
      hasInitializedRef.current = true;
      createInitialMessage();
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resourcesLoading, option]);

  const toggleSelect = (id) => {
    setSelectedIds((prev) =>
      prev.includes(id) ? prev.filter((f) => f !== id) : [...prev, id]
    );
  };

  const handleSend = async () => {
    if (!inputMessage.trim()) return;
    if (isSendingRef.current || isLoading) return;
    isSendingRef.current = true;
    userScrolledRef.current = false;
    const newMsg = { type: "user", text: inputMessage };
    setChatMessages((prev) => [...prev, newMsg]);
    setInputMessage("");
    // Reset textarea height
    if (textareaRef.current) {
      textareaRef.current.style.height = `${COMPOSER_ROW_HEIGHT}px`;
    }
    setIsLoading(true);

    try {
      if (!lastResponseId) {
        throw new Error("No active chat history");
      }

      const courseId = localStorage.getItem('currentCourseId');
      if (!courseId) {
        throw new Error("No course ID found");
      }

      // Continue the conversation with the backend
      const response = await assetService.continueAssetChat(courseId, option, lastResponseId, inputMessage, setStreamingText);


      if (response && response.response) {
        setLastResponseId(response.response_id);
        const normalizedResponse = normalizeEscapes(response.response);
        const formattedResponse = option === 'mark-scheme'
          ? formatMarkSchemeResponse(normalizedResponse)
          : normalizedResponse;
        const botResponse = {
          type: "bot",
          text: formattedResponse
        };
        await settleStream(formattedResponse);
        setChatMessages((prev) => [...prev, botResponse]);
      }
    } catch (err) {
      console.error("Chat error:", err);
      console.error("Error details:", err.message);
      const errorResponse = {
        type: "bot",
        text: `⚠️ Sorry, I encountered an error: ${err.message || 'Unknown error'}. Please try again.`
      };
      setChatMessages((prev) => [...prev, errorResponse]);
    } finally {
      setStreamingText("");
      setIsLoading(false);
      isSendingRef.current = false;
    }
  };

  const handleSaveToAsset = (message) => {
    setSaveModalMessage(message);
    setAssetName("");
    setShowSaveModal(true);
  };

  const handleSaveAssetConfirm = async () => {
    if (isSavingAsset) return;
    setIsSavingAsset(true);
    try {
      const courseId = localStorage.getItem('currentCourseId');
      if (!courseId) {
        console.error('No course ID found');
        return;
      }

      // Get existing assets to check for conflicts
      const existingAssetsData = await assetService.getAssets(courseId);
      const existingAssets = existingAssetsData.assets || [];
      const existingAssetNames = existingAssets.map(asset => asset.asset_name);

      // Resolve name conflict
      const finalAssetName = resolveNameConflict(assetName.trim(), existingAssetNames);

      // Update the asset name in the input if it was changed
      if (finalAssetName !== assetName.trim()) {
        setAssetName(finalAssetName);
      }

      const assetType = option;

      await assetService.saveAsset(courseId, finalAssetName, assetType, saveModalMessage);

      // Close modal and reset
      setShowSaveModal(false);
      setSaveModalMessage("");
      setAssetName("");
    } catch (error) {
      console.error("Error saving asset:", error);
      alert(`Failed to save asset: ${error?.message || 'Unknown error'}`);
    } finally {
      setIsSavingAsset(false);
    }
  };

  const handleSaveAssetCancel = () => {
    setShowSaveModal(false);
    setSaveModalMessage("");
    setAssetName("");
  };

  const handleSaveToResource = (message) => {
    setResourceSaveMessage(message || "");
    setResourceFileName("");
    setShowSaveResourceModal(true);
  };

  const handleSaveResourceConfirm = async () => {
    if (isSavingResourceRef.current || isSavingResource) return;
    isSavingResourceRef.current = true;
    setIsSavingResource(true);
    try {
      const courseId = localStorage.getItem('currentCourseId');
      if (!courseId) return;

      // Get existing resource names to check for conflicts
      const existingResourceNames = getAllResourceNames(resources);

      // Resolve name conflict
      const baseResourceName = (resourceFileName || '').trim() || 'document';
      const finalResourceName = resolveNameConflict(baseResourceName, existingResourceNames);

      // Update the resource name in the input if it was changed
      if (finalResourceName !== baseResourceName) {
        setResourceFileName(finalResourceName);
      }

      console.log('Saving chat message as resource:', finalResourceName);
      console.log('Content length:', resourceSaveMessage?.length || 0);

      // Use the same endpoint as AssetSubCard - save content as text resource
      const result = await assetService.saveAssetAsResource(courseId, finalResourceName, resourceSaveMessage || '');
      console.log('Save as resource result:', result);

      // Refresh resources list
      const resourcesData = await getAllResources(courseId);
      setResources(resourcesData.resources);

      setShowSaveResourceModal(false);
      setResourceFileName("");
      setResourceSaveMessage("");
    } catch (e) {
      console.error('Failed to save to resources', e);
      alert(`Failed to save to resources: ${e.message}`);
    } finally {
      isSavingResourceRef.current = false;
      setIsSavingResource(false);
    }
  };

  const handleSaveResourceCancel = () => {
    setShowSaveResourceModal(false);
    setResourceFileName("");
    setResourceSaveMessage("");
  };

  const handleFileUpload = () => {
    // For mock data, we'll just log the upload
  };

  // Add this handler to refresh resources after adding
  const handleAddResources = async (files) => {
    setShowAddResourceModal(false);
    const courseId = localStorage.getItem('currentCourseId');
    if (!courseId || !files.length) return;
    try {
      setIsUploadingResources(true);
      // PDF/image pipeline: raw bytes stored in Mongo; PDFs go directly to the model.
      const uploadResult = await extractResourceImages(courseId, files);
      // Surface files the backend skipped (too large, name clash, save failure)
      if (uploadResult?.message?.includes('skipped')) {
        alert(uploadResult.message);
      }
      // Refresh resources
      const resourcesData = await getAllResources(courseId);
      setResources(resourcesData.resources);
    } catch (err) {
      console.error('Error uploading resources from modal:', err);
      alert(`Failed to upload resources: ${err.message || 'Unknown error'}`);
    } finally {
      setIsUploadingResources(false);
    }
  };

  const handleDeleteResource = async (resourceId) => {
    const courseId = localStorage.getItem('currentCourseId');
    if (!courseId) return;
    try {
      await deleteResourceApi(courseId, resourceId);
      // Refresh resources
      const resourcesData = await getAllResources(courseId);
      setResources(resourcesData.resources);
    } catch (err) {
      alert('Failed to delete resource.');
    }
  };

  return (
    <AssetStudioLayout
      title={title}
      rightPanel={
        <KnowledgeBase
          resources={resources}
          showCheckboxes
          selected={selectedIds}
          onSelect={toggleSelect}
          onSelectAll={(ids) => setSelectedIds(ids)}
          fileInputRef={{ current: null }}
          onFileChange={handleFileUpload}
          onAddResource={() => setShowAddResourceModal(true)}
          onDelete={handleDeleteResource}
          courseId={localStorage.getItem('currentCourseId')}
          isUploading={isUploadingResources}
          fillHeight
        />
      }
    >
      {/* Header: what is being generated + how many sources feed it */}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          gap: 12,
          paddingBottom: 12,
          borderBottom: "1px solid #eef2f7",
          flexShrink: 0
        }}
      >
        <div style={{ fontSize: 18, fontWeight: 600, letterSpacing: "-0.01em", color: "#111827" }}>{title}</div>
        <div style={{ fontSize: 13, color: "#94a3b8" }}>
          {selectedIds.length} {selectedIds.length === 1 ? "source" : "sources"} selected
        </div>
      </div>

      {/* Transcript (the only scrollable region on this side) */}
      <div
        ref={scrollRef}
        onWheel={markUserScrolled}
        onTouchMove={markUserScrolled}
        onMouseDown={(e) => { if (e.target === scrollRef.current) markUserScrolled(); /* scrollbar drag */ }}
        className="cc-scroll"
        style={{
          flex: 1,
          minHeight: 0,
          overflowY: "auto",
          overflowX: "hidden",
          display: "flex",
          flexDirection: "column",
          gap: 18,
          // Right padding keeps bubbles clear of the scrollbar
          padding: "16px 18px 12px 4px"
        }}
      >
        <style>{`
          @keyframes blink { 0% { opacity: 0.2 } 20% { opacity: 1 } 100% { opacity: 0.2 } }
          @keyframes caret { 0%, 45% { opacity: 1 } 50%, 100% { opacity: 0 } }
          @keyframes ccFadeIn { from { opacity: 0; transform: translateY(4px) } to { opacity: 1; transform: none } }
          /* Streaming caret sits at the end of the last line of text (not on a line of
             its own); tables and code blocks get none rather than a stray cell. */
          .cc-stream > :last-child:not(ul):not(ol):not(pre):not(:has(table))::after,
          .cc-stream > :is(ul, ol):last-child > li:last-child::after {
            content: "";
            display: inline-block;
            width: 7px;
            height: 1.05em;
            margin-left: 3px;
            background: #2563eb;
            border-radius: 1px;
            vertical-align: -0.15em;
            animation: caret 1s step-end infinite;
          }
          @media (prefers-reduced-motion: reduce) {
            .cc-stream > *::after, .cc-stream li::after { animation: none !important; }
          }
        `}</style>

        {chatMessages.length === 0 && !isBusy && (
          <div style={{ margin: "auto", textAlign: "center", color: "#94a3b8", fontSize: 15, maxWidth: 380, lineHeight: 1.7 }}>
            Select resources in the Knowledge Base and ask below to generate your {title.toLowerCase()}.
          </div>
        )}

        {chatMessages.map((msg, i) => (
          msg.type === "user" ? (
            <div key={i} style={{ display: "flex", justifyContent: "flex-end", minWidth: 0 }}>
              <div
                style={{
                  maxWidth: "72%",
                  background: "#e8f1ff",
                  border: "1px solid #d5e5fb",
                  borderRadius: "14px 14px 4px 14px",
                  padding: "11px 16px",
                  color: "#1f2937",
                  fontSize: 16,
                  lineHeight: 1.65,
                  textAlign: "left",
                  whiteSpace: "pre-wrap",
                  wordBreak: "break-word"
                }}
              >
                {msg.text}
              </div>
            </div>
          ) : (
            <div key={i} ref={i === chatMessages.length - 1 && !isBusy ? responseStartRef : undefined} style={{ width: "100%", minWidth: 0 }}>
              {msg.type === "bot-image" ? (
                <img src={msg.url} alt="Asset preview" style={{ maxWidth: "100%", borderRadius: 8 }} />
              ) : (
                <>
                  <div style={{ wordBreak: "break-word" }}>
                    <BotMarkdown text={msg.text} components={botComponents} />
                  </div>
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 16,
                      marginTop: 12,
                      paddingTop: 12,
                      borderTop: "1px solid #f1f5f9",
                      fontSize: 16,
                      color: "#94a3b8"
                    }}
                  >
                    <DownloadButton
                      courseId={localStorage.getItem('currentCourseId')}
                      filename={(title || 'asset').toString().replace(/[^a-zA-Z0-9-_]/g, '_')}
                      content={msg.text}
                      renderTrigger={(open) => (
                        <FaDownload
                          title="Download"
                          style={{ cursor: "pointer" }}
                          onClick={open}
                        />
                      )}
                    />
                    <FaFolderPlus
                      title="Save to Asset"
                      style={{ cursor: "pointer" }}
                      onClick={() => handleSaveToAsset(msg.text)}
                    />
                    <FaSave
                      title="Save to Resource"
                      style={{ cursor: "pointer" }}
                      onClick={() => handleSaveToResource(msg.text)}
                    />
                  </div>
                </>
              )}
            </div>
          )
        ))}

        {/* Live stream of the answer being written, else a typing indicator */}
        {isBusy && (
          streamingText ? (
            <div
              ref={responseStartRef}
              aria-live="polite"
              aria-busy="true"
              style={{ width: "100%", minWidth: 0, wordBreak: "break-word", animation: "ccFadeIn 0.25s ease-out" }}
            >
              {/* Fall back to the raw stream so text still shows if the reveal stalls */}
              <BotMarkdown className="cc-stream" text={stripStreamingImages(revealedStream || streamingText)} components={botComponents} />
            </div>
          ) : (
            <div aria-label="Assistant is typing" style={{ display: "flex", alignItems: "center", gap: 8, color: "#94a3b8", fontSize: 15 }}>
              <span style={{ display: "inline-block", width: 6, height: 6, background: "#bbb", borderRadius: "50%", animation: "blink 1.4s infinite" }}></span>
              <span style={{ display: "inline-block", width: 6, height: 6, background: "#bbb", borderRadius: "50%", animation: "blink 1.4s infinite", animationDelay: "0.2s" }}></span>
              <span style={{ display: "inline-block", width: 6, height: 6, background: "#bbb", borderRadius: "50%", animation: "blink 1.4s infinite", animationDelay: "0.4s" }}></span>
              {chatMessages.length === 0 && <span style={{ marginLeft: 4 }}>Generating {title.toLowerCase()}…</span>}
            </div>
          )
        )}
      </div>

      {/* Composer */}
      <div style={{ flexShrink: 0, paddingTop: 12, borderTop: "1px solid #eef2f7" }}>
        <div
          style={{
            display: "flex",
            gap: 8,
            alignItems: "flex-end",
            background: "#f8fafc",
            border: "1px solid #e2e8f0",
            borderRadius: 12,
            padding: 8
          }}
        >
          <textarea
            ref={textareaRef}
            value={inputMessage}
            onChange={(e) => setInputMessage(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                if (!isLoading && inputMessage.trim()) {
                  handleSend();
                }
              }
            }}
            placeholder={isLoading ? "Generating response…" : "Type your message..."}
            style={{
              flex: 1,
              // border-box so the auto-resize below can set height = scrollHeight
              // without the vertical padding being counted twice.
              boxSizing: "border-box",
              padding: "9px 12px",
              border: "none",
              outline: "none",
              background: "transparent",
              color: "#1f2937",
              fontSize: 16,
              height: COMPOSER_ROW_HEIGHT,
              minHeight: COMPOSER_ROW_HEIGHT,
              maxHeight: 140,
              resize: "none",
              overflow: "auto",
              fontFamily: "inherit",
              lineHeight: "1.5",
              whiteSpace: "pre-wrap",
              wordWrap: "break-word"
            }}
            rows={1}
            onInput={(e) => {
              // Grow only once the text actually wraps to a new line
              e.target.style.height = `${COMPOSER_ROW_HEIGHT}px`;
              const newHeight = Math.min(Math.max(e.target.scrollHeight, COMPOSER_ROW_HEIGHT), 140);
              e.target.style.height = newHeight + 'px';
            }}
          />
          <button
            onClick={handleSend}
            disabled={isLoading || !inputMessage.trim()}
            style={{
              // Same height as the collapsed textarea so the two line up exactly
              height: COMPOSER_ROW_HEIGHT,
              minWidth: 84,
              padding: "0 20px",
              display: "inline-flex",
              alignItems: "center",
              justifyContent: "center",
              borderRadius: 8,
              background: isLoading || !inputMessage.trim() ? "#cbd5e1" : "#2563eb",
              color: "#fff",
              border: "none",
              fontSize: 15,
              fontWeight: 500,
              lineHeight: 1,
              cursor: isLoading || !inputMessage.trim() ? "not-allowed" : "pointer",
              transition: "background 0.15s ease"
            }}
          >
            {isLoading ? "…" : "Send"}
          </button>
        </div>
        <div style={{ fontSize: 12.5, color: "#94a3b8", marginTop: 7 }}>
          Enter to send · Shift + Enter for a new line
        </div>
      </div>

      {/* Save Asset Modal */}
      {showSaveModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000
          }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 12,
              padding: 24,
              width: "400px",
              maxWidth: "90vw",
              boxShadow: "0 4px 20px rgba(0, 0, 0, 0.15)"
            }}
          >
            <h3 style={{ margin: "0 0 16px 0", fontSize: 18, fontWeight: 600 }}>
              Save Asset
            </h3>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 8, fontWeight: 500 }}>
                Asset Name:
              </label>
              <input
                type="text"
                value={assetName}
                onChange={(e) => setAssetName(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: 6,
                  border: "1px solid #ccc",
                  fontSize: 14,
                  boxSizing: "border-box"
                }}
                placeholder="Enter asset name..."
              />
            </div>

            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button
                onClick={handleSaveAssetCancel}
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  border: "1px solid #ccc",
                  background: "#fff",
                  cursor: "pointer",
                  fontSize: 14
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveAssetConfirm}
                disabled={!assetName.trim() || isSavingAsset}
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  border: "none",
                  background: assetName.trim() && !isSavingAsset ? "#2563eb" : "#ccc",
                  color: "#fff",
                  cursor: assetName.trim() && !isSavingAsset ? "pointer" : "not-allowed",
                  fontSize: 14,
                  fontWeight: 500
                }}
              >
                {isSavingAsset ? "Saving..." : "Save Asset"}
              </button>
            </div>
          </div>
        </div>
      )}
      {showSaveResourceModal && (
        <div
          style={{
            position: "fixed",
            top: 0,
            left: 0,
            right: 0,
            bottom: 0,
            background: "rgba(0, 0, 0, 0.5)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            zIndex: 1000
          }}
        >
          <div
            style={{
              background: "#fff",
              borderRadius: 12,
              padding: 24,
              width: "400px",
              maxWidth: "90vw",
              boxShadow: "0 4px 20px rgba(0, 0, 0, 0.15)"
            }}
          >
            <h3 style={{ margin: "0 0 16px 0", fontSize: 18, fontWeight: 600 }}>
              Save to Resource
            </h3>

            <div style={{ marginBottom: 16 }}>
              <label style={{ display: "block", marginBottom: 8, fontWeight: 500 }}>
                Resource Name:
              </label>
              <input
                type="text"
                value={resourceFileName}
                onChange={(e) => setResourceFileName(e.target.value)}
                style={{
                  width: "100%",
                  padding: "10px 12px",
                  borderRadius: 6,
                  border: "1px solid #ccc",
                  fontSize: 14,
                  boxSizing: "border-box"
                }}
                placeholder="Enter resource name (e.g., Course Notes)"
              />
            </div>

            <div style={{ display: "flex", gap: 12, justifyContent: "flex-end" }}>
              <button
                onClick={handleSaveResourceCancel}
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  border: "1px solid #ccc",
                  background: "#fff",
                  cursor: "pointer",
                  fontSize: 14
                }}
              >
                Cancel
              </button>
              <button
                onClick={handleSaveResourceConfirm}
                disabled={!resourceFileName.trim() || isSavingResource}
                style={{
                  padding: "8px 16px",
                  borderRadius: 6,
                  border: "none",
                  background: resourceFileName.trim() && !isSavingResource ? "#2563eb" : "#ccc",
                  color: "#fff",
                  cursor: resourceFileName.trim() && !isSavingResource ? "pointer" : "not-allowed",
                  fontSize: 14,
                  fontWeight: 500
                }}
              >
                {isSavingResource ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        </div>
      )}
      <AddResourceModal
        open={showAddResourceModal}
        onClose={() => setShowAddResourceModal(false)}
        onAdd={handleAddResources}
        onRefresh={async () => {
          const courseId = localStorage.getItem('currentCourseId');
          if (courseId) {
            try {
              const resourcesData = await getAllResources(courseId);
              setResources(resourcesData.resources);
            } catch (e) { console.error(e); }
          }
        }}
      />
    </AssetStudioLayout>
  );
}
