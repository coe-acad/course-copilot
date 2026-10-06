from logging import log
import logging
import re
import io
import base64
import asyncio
import time
from typing import Optional
from ..config.settings import settings
from fastapi import APIRouter, HTTPException, Depends, Response
from pydantic import BaseModel
from datetime import datetime
from ..utils.verify_token import verify_token
from ..utils.prompt_parser import PromptParser
from ..utils.openai_client import client
from ..utils.text_to_pdf import text_to_pdf
from ..utils.text_to_docx import text_to_docx
from ..utils.text_to_xlsx import text_to_xlsx
from ..utils.sprint_plan import build_sprint_plan
from ..services.mongo import get_course, create_asset, get_assets_by_course_id, get_asset_by_course_id_and_asset_name, delete_asset_from_db, create_resource, get_resources_by_course_id, get_resource_by_course_id_and_resource_name, get_user_display_name, get_resource_images_for_names, get_resource_image_ids_for_course, get_resource_pdf, get_resource_pdfs_meta_for_names, save_resource_pdf
from ..services.task_manager import task_manager, TaskStatus
from .resources import ensure_unique_name, _MAX_PDF_BYTES
from PyPDF2 import PdfReader
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)
router = APIRouter()

class AssetViewResponse(BaseModel):
    asset_name: str
    asset_type: str
    asset_category: str
    asset_content: str
    asset_last_updated_by: str
    asset_last_updated_at: str
    created_by_user_id: Optional[str] = None

class AssetPromptRequest(BaseModel):
    user_prompt: str

class AssetRequest(BaseModel):
    file_names: list[str]
    course_description: Optional[str] = None

class AssetResponse(BaseModel):
    response: str

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    metadata: Optional[dict] = None
    # Text streamed so far while status is pending/processing (live preview only)
    partial: Optional[str] = None

class AssetCreateResponse(BaseModel):
    message: str

class AssetCreateRequest(BaseModel):
    content: str
    created_at: Optional[str] = None

class Asset(BaseModel):
    asset_name: str
    asset_type: str
    asset_category: str
    asset_content: str
    asset_last_updated_by: str
    asset_last_updated_at: str
    created_by_user_id: Optional[str] = None

class AssetListResponse(BaseModel):
    assets: list[Asset]

class ImageRequest(BaseModel):
    prompt: str

class ImageResponse(BaseModel):
    image_url: str

class TextToPdfRequest(BaseModel):
    content: str
    filename: Optional[str] = None

class TextToDocxRequest(BaseModel):
    content: str
    filename: Optional[str] = None

# Generation runs here instead of FastAPI BackgroundTasks. A background task runs
# inside the request's lifecycle, so uvicorn won't read the next request on that
# keep-alive connection until it finishes; the browser reuses the connection for
# the first /tasks poll, which then hangs for the whole generation (no streaming).
_generation_executor = ThreadPoolExecutor(max_workers=8, thread_name_prefix="asset-gen")

class AssetChatStreamHandler:
    """Custom event handler for OpenAI Responses API streaming.
    
    Processes streaming events from the Responses API and accumulates
    the response text and response ID for later use.

    When ``task_id`` is given, the accumulated text is published to the task every
    ``_PARTIAL_FLUSH_CHARS`` characters so the client can render it live while the
    model is still writing.
    """
    _PARTIAL_FLUSH_CHARS = 48

    def __init__(self, label: str = "", task_id: Optional[str] = None):
        self.response_text = ""
        self.response_id = None
        self.label = label
        self.task_id = task_id
        self._published_len = 0

    def handle(self, event):
        if event.type == "response.created":
            self.response_id = event.response.id

        elif event.type == "response.output_text.delta":
            self.response_text += event.delta
            if self.task_id and len(self.response_text) - self._published_len >= self._PARTIAL_FLUSH_CHARS:
                self._published_len = len(self.response_text)
                task_manager.set_partial(self.task_id, self.response_text)

        elif event.type == "response.completed":
            self.response_id = event.response.id

        elif event.type == "response.error":
            print(f"[ERROR] {event.error}")


def construct_input_variables(course: dict, file_names: list[str], course_description: Optional[str] = None) -> dict:
    input_variables = {
        "course_name": course.get("name", ""),
        "course_level": course.get("settings", {}).get("course_level", ""),
        "study_area": course.get("settings", {}).get("study_area", ""),
        "pedagogical_components": course.get("settings", {}).get("pedagogical_components", ""),
        "file_names": file_names,
        "course_description": course_description or ""
    }
    return input_variables


# Selected files with these extensions are attached as vision figures, so having no
# stored text is expected rather than a problem.
_IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")


def _resolve_selected_text_sections(course_id: str, file_names: list, skip_names: set) -> list:
    """Resolve each selected file (resource or saved asset) to its stored text.

    With no file_search tool attached, this injected text plus the directly-attached
    Mongo PDFs are the only source material the model can read. Names in
    ``skip_names`` (files already attached verbatim as PDFs) are skipped.
    """
    sections = []
    for fname in file_names:
        if not fname or fname in skip_names:
            continue
        content = ""
        resource = get_resource_by_course_id_and_resource_name(course_id, fname)
        if resource and resource.get("content"):
            content = resource["content"]
        else:
            asset = get_asset_by_course_id_and_asset_name(course_id, fname)
            if asset and asset.get("asset_content"):
                content = asset["asset_content"]
        if content:
            sections.append(f"### {fname}\n{content}")
            logger.info(f"[selection] injected content for selected file '{fname}' ({len(content)} chars)")
        elif fname.lower().endswith(_IMAGE_EXTENSIONS):
            # Images carry no text by design: they reach the model as vision input
            # (and as image_ref:<id> figures), not through this text injection.
            logger.info(f"[selection] '{fname}' is an image; attached as a figure rather than text")
        else:
            logger.warning(f"[selection] no stored text content for selected file '{fname}'; it is not visible to the model")
    return sections


# Cap on figures attached as vision input per generation (token/cost guard).
_MAX_FIGURES = 12

# Direct-to-model PDF limits per chat (OpenAI accepts ~100 pages / ~32 MB of file
# content per request; we stay safely under that).
_MAX_CHAT_PDFS = 10
_MAX_CHAT_PDF_BYTES = 30 * 1024 * 1024
_MAX_CHAT_PDF_PAGES = 100

# Any inline markdown image. Used to sanitize model output so ONLY real figures
# survive: image_ref:<id> -> served URL, every other src is stripped.
_ANY_IMAGE_MD = re.compile(r"!\[([^\]]*)\]\(\s*([^)]*?)\s*\)")


def _resolve_image_refs(text: str, course_id: str, allowed_ids: set) -> str:
    """Sanitize image links in generated content so only REAL figures render.

    - ``![alt](image_ref:<id>)`` with a known id -> absolute served-image URL, so
      the picture renders in the chat, the saved view, and PDF/DOCX exports.
    - any other image (unknown id, or a src the model invented such as
      ``attachment:x`` or an external ``https://…`` URL) -> the image markdown is
      removed, so a broken image is never shown anywhere.
    """
    if not text:
        return text
    base = settings.PUBLIC_BASE_URL.rstrip("/")

    def _sub(match):
        alt, src = match.group(1), (match.group(2) or "").strip()
        if src.startswith("image_ref:"):
            image_id = src[len("image_ref:"):].strip()
            if image_id in allowed_ids:
                return f"![{alt}]({base}/api/courses/{course_id}/images/{image_id})"
            logger.warning(f"[figures] removed unknown image_ref:{image_id}")
            return ""
        logger.warning(f"[figures] removed invented image src={src[:60]!r}")
        return ""

    return _ANY_IMAGE_MD.sub(_sub, text)


def _process_asset_chat_background(task_id: str, course_id: str, asset_type_name: str, file_names: list, course_description: Optional[str], user_id: str):
    """Background task to process asset chat generation"""
    try:
        task_manager.mark_processing(task_id)
        logger.info(f"Starting background task {task_id} for asset '{asset_type_name}'")
        
        course = get_course(course_id)
        logger.info(f"[DEBUG] Course ID: {course_id}")
        logger.info(f"[DEBUG] Asset Type: {asset_type_name}")
        logger.info(f"[DEBUG] File Names: {file_names}")
        logger.info(f"[DEBUG] Course Description Present: {bool(course_description)}")

        if not course:
            task_manager.mark_failed(task_id, "Course not found")
            return
        # Check if mark-scheme and extract questions first
        extracted_questions = ""
        systemPrompt = PromptParser().render_prompt("app/prompts/system/overall_context.json" , {})

        # Directly-uploaded PDFs (stored in Mongo) are sent to the model verbatim so it
        # reads the real documents. This is the ONLY file access the model has — there
        # is no file_search/vector store attached, so the selection is a hard boundary.
        # Built up-front so the mark-scheme question extraction can attach them too.
        pdf_inputs = []
        try:
            for _name in file_names:
                rec = get_resource_pdf(course_id, _name)
                if rec and rec.get("pdf_bytes"):
                    b64 = base64.b64encode(bytes(rec["pdf_bytes"])).decode("ascii")
                    pdf_inputs.append({
                        "filename": _name,
                        "data_uri": f"data:application/pdf;base64,{b64}",
                    })
        except Exception as pdf_err:
            logger.warning(f"[pdf] lookup failed: {pdf_err}")
        if pdf_inputs:
            logger.info(f"[pdf] attaching {len(pdf_inputs)} PDF(s) directly to the model")
        pdf_names = {p["filename"] for p in pdf_inputs}
        if asset_type_name == "mark-scheme":
            # First extract questions using qp-extraction
            input_variables_qp = construct_input_variables(course, file_names)
            parser_qp = PromptParser()
            prompt_qp = parser_qp.get_asset_prompt("qp-extraction", input_variables_qp)

            # The extraction model has no file_search: give it the selected files
            # directly — stored text inline, Mongo PDFs attached verbatim.
            qp_sections = _resolve_selected_text_sections(course_id, file_names, pdf_names)
            if qp_sections:
                prompt_qp += (
                    "\n\n---\n"
                    "FULL CONTENT OF THE SELECTED FILES (authoritative source material — "
                    "treat this as the content of the files named above and use it directly):\n\n"
                    + "\n\n".join(qp_sections)
                )

            qp_content = prompt_qp
            if pdf_inputs:
                qp_content = [{"type": "input_text", "text": prompt_qp}]
                for p in pdf_inputs:
                    qp_content.append({"type": "input_file", "filename": p["filename"], "file_data": p["data_uri"]})

            handler_qp = AssetChatStreamHandler(label="Question Extraction")

            try:
                with client.responses.stream(
                    model=settings.OPENAI_MODEL,
                    input=[
                        {"role": "system", "content": systemPrompt},
                        {"role": "user", "content": qp_content}
                    ]
                ) as stream:
                    for event in stream:
                        handler_qp.handle(event)
            except Exception as stream_error:
                logger.warning(f"Stream interrupted during question extraction in task {task_id}: {stream_error}")
                # Continue - we can still get the response from messages
            
            try:
                extracted_questions = handler_qp.response_text
                if not extracted_questions or len(extracted_questions.strip()) == 0:
                    raise Exception("No response found in question extraction")
                logger.info(f"Extracted questions: {extracted_questions}")
            except Exception as msg_error:
                logger.error(f"Error retrieving extracted questions: {msg_error}")
                # Don't fail the entire task - continue without extracted questions
                extracted_questions = ""

        # If sprint-plan is generating and no course description text was provided, try to resolve it from the course or resources.
        if asset_type_name == "sprint-plan" and not course_description:
            course_description = course.get("description", "") or course_description
            if not course_description:
                for file_name in file_names:
                    if file_name and "Course_Description" in file_name:
                        resource = get_resource_by_course_id_and_resource_name(course_id, file_name)
                        if resource and resource.get("content"):
                            course_description = resource["content"]
                            break
                # If still no description, use course name as fallback
                if not course_description:
                    course_description = course.get("name", "Course") + " - Course Description"

        # For sprint-plan, resolve selected assets/resources to raw content so the model can actually use them.
        sprint_plan_sources = {}
        if asset_type_name == "sprint-plan":
            def _resolve_source_content(source_name: Optional[str]) -> str:
                if not source_name:
                    return ""
                resource = get_resource_by_course_id_and_resource_name(course_id, source_name)
                if resource and resource.get("content"):
                    return resource["content"]
                asset = get_asset_by_course_id_and_asset_name(course_id, source_name)
                if asset and asset.get("asset_content"):
                    return asset["asset_content"]
                return ""

            course_outcomes_name = file_names[1] if len(file_names) > 1 else None
            modules_name = file_names[2] if len(file_names) > 2 else None
            po_pso_name = file_names[3] if len(file_names) > 3 else None

            sprint_plan_sources = {
                "course_outcomes_content": _resolve_source_content(course_outcomes_name),
                "modules_content": _resolve_source_content(modules_name),
                "po_pso_content": _resolve_source_content(po_pso_name),
            }

        # For sprint-plan, build deterministically from selected content (no LLM dependency)
        if asset_type_name == "sprint-plan":
            course_name = course.get("name", "")

            # DEBUG: Log what content we're working with
            co_content = sprint_plan_sources.get("course_outcomes_content", "")
            modules_content = sprint_plan_sources.get("modules_content", "")
            po_pso_content = sprint_plan_sources.get("po_pso_content", "")

            logger.info(f"[SPRINT_PLAN_DEBUG] CO content length: {len(co_content)}")
            logger.info(f"[SPRINT_PLAN_DEBUG] Modules content length: {len(modules_content)}")
            logger.info(f"[SPRINT_PLAN_DEBUG] PO-PSO content length: {len(po_pso_content)}")
            logger.info(f"[SPRINT_PLAN_DEBUG] CO content preview: {co_content[:200] if co_content else 'EMPTY'}")
            logger.info(f"[SPRINT_PLAN_DEBUG] Modules content preview: {modules_content[:200] if modules_content else 'EMPTY'}")

            sprint_plan_text = build_sprint_plan(
                course_name=course_name,
                course_description=course_description or "",
                course_outcomes_content=co_content,
                modules_content=modules_content,
                po_pso_content=po_pso_content,
            )
            # Fill CO-PO-PSO mapping + textbooks + references using LLM only for those sections
            try:
                ai_prompt = PromptParser().render_prompt(
                    "app/prompts/asset/sprint-plan-ai.json",
                    {
                        "course_name": course_name,
                        "course_description": course_description or "",
                        "course_outcomes_content": sprint_plan_sources.get("course_outcomes_content", ""),
                        "modules_content": sprint_plan_sources.get("modules_content", ""),
                        "po_pso_content": sprint_plan_sources.get("po_pso_content", ""),
                    },
                )
                ai_response = client.chat.completions.create(
                    model=settings.OPENAI_MODEL,
                    messages=[
                        {"role": "system", "content": systemPrompt},
                        {"role": "user", "content": ai_prompt},
                    ],
                    temperature=0.3,
                )
                ai_text = (ai_response.choices[0].message.content or "").strip()
                logger.info(f"Sprint plan AI response length: {len(ai_text)} chars")
                if not ai_text:
                    logger.warning("Sprint plan AI response is empty")
            except Exception as ai_error:
                logger.error(f"Sprint plan AI section generation failed: {ai_error}", exc_info=True)
                ai_text = ""

            if ai_text:
                def _section(text: str, header: str) -> str:
                    pattern = rf"\*\*{re.escape(header)}\*\*\s*([\s\S]*?)(?=\*\*|$)"
                    match = re.search(pattern, text, re.IGNORECASE)
                    return match.group(1).strip() if match else ""

                mapping_section = _section(ai_text, "CO-PO-PSO Mapping Table:")
                textbooks_section = _section(ai_text, "3 Textbook Titles:")
                references_section = _section(ai_text, "3 Reference Books:")

                if mapping_section:
                    sprint_plan_text = sprint_plan_text.replace("<<AI_CO_PO_PSO_TABLE>>", mapping_section)
                if textbooks_section:
                    sprint_plan_text = sprint_plan_text.replace("<<AI_TEXTBOOKS>>", textbooks_section)
                if references_section:
                    sprint_plan_text = sprint_plan_text.replace("<<AI_REFERENCES>>", references_section)

            # Fallbacks if AI sections are still missing
            if "<<AI_CO_PO_PSO_TABLE>>" in sprint_plan_text:
                blank_headers = ["Course", "PO1", "PO2", "PO3", "PO4", "PO5", "PO6", "PO7", "PO8", "PO9", "PO10", "PO11", "PO12", "PSO1", "PSO2", "PSO3"]
                blank_table = [
                    "| " + " | ".join(blank_headers) + " |",
                    "|" + "|".join(["---"] * len(blank_headers)) + "|",
                    "| CO1 | " + " | ".join([""] * (len(blank_headers) - 1)) + " |",
                    "| CO2 | " + " | ".join([""] * (len(blank_headers) - 1)) + " |",
                    "| CO3 | " + " | ".join([""] * (len(blank_headers) - 1)) + " |",
                    "| CO4 | " + " | ".join([""] * (len(blank_headers) - 1)) + " |",
                ]
                sprint_plan_text = sprint_plan_text.replace("<<AI_CO_PO_PSO_TABLE>>", "\n".join(blank_table))
            if "<<AI_TEXTBOOKS>>" in sprint_plan_text:
                sprint_plan_text = sprint_plan_text.replace("<<AI_TEXTBOOKS>>", "1. \n2. \n3. ")
            if "<<AI_REFERENCES>>" in sprint_plan_text:
                sprint_plan_text = sprint_plan_text.replace("<<AI_REFERENCES>>", "1. \n2. \n3. ")

            result = {
                "response": sprint_plan_text.strip(),
                "response_id": None
            }
            task_manager.mark_completed(task_id, result)
            logger.info(f"Completed background task {task_id} for asset '{asset_type_name}'")
            return

        # Prepare prompt
        input_variables = construct_input_variables(
            course,
            file_names,
            course_description
        )

        if sprint_plan_sources:
            input_variables.update(sprint_plan_sources)

        # Add extracted_questions to input_variables if mark-scheme
        if asset_type_name == "mark-scheme":
            input_variables["extracted_questions"] = extracted_questions

        # Figures (directly-uploaded images) available to this generation, resolved
        # from the selected files for EVERY asset type. Resolved BEFORE the prompt is
        # rendered so prompts that declare an {{available_images}} variable (question
        # paper) and the AVAILABLE FIGURES block below share one source of truth.
        figures = []
        allowed_image_ids = set()

        # Directly-uploaded png/jpeg resources stored in Mongo (base64).
        try:
            mongo_records = get_resource_images_for_names(course_id, file_names)
        except Exception as m_err:
            mongo_records = []
            logger.warning(f"[figures] mongo lookup failed: {m_err}")

        for rec in mongo_records[:_MAX_FIGURES]:
            image_id = rec.get("image_id")
            if not image_id:
                continue
            b64 = rec.get("image_base64")
            mime = rec.get("image_mime") or "image/png"
            figures.append({
                "image_id": image_id,
                "caption": (rec.get("resource_name") or "").strip(),
                "resource_name": rec.get("resource_name") or "",
                "page": None,
                "data_uri": f"data:{mime};base64,{b64}" if b64 else None,
            })
            allowed_image_ids.add(image_id)
        if len(mongo_records) > _MAX_FIGURES:
            logger.warning(f"[figures] {len(mongo_records)} available; only the first {_MAX_FIGURES} are used")

        # Expose the same figures to prompt templates that declare the variable.
        # image_ref:<id> is the ONLY image reference the model may emit — it is
        # rewritten to a real served URL by _resolve_image_refs after generation,
        # and anything else is stripped.
        if figures:
            input_variables["available_images"] = "\n\n".join(
                f"Filename: {f['resource_name']}\nImage Reference: image_ref:{f['image_id']}"
                for f in figures
            )
        else:
            input_variables["available_images"] = "No image resources were selected."

        parser = PromptParser()
        prompt = parser.get_asset_prompt(
            asset_type_name,
            input_variables
        )


        # Inject the ACTUAL content of the selected files into the prompt. Selection
        # otherwise only passes file NAMES, and with no file_search tool attached the
        # injected text plus the directly-attached Mongo PDFs are the model's ONLY
        # source material. Sprint-plan resolves its sources itself above.
        if asset_type_name != "sprint-plan":
            resolved_sections = _resolve_selected_text_sections(course_id, file_names, pdf_names)
            if resolved_sections:
                prompt += (
                    "\n\n---\n"
                    "FULL CONTENT OF THE SELECTED FILES (authoritative source material — "
                    "treat this as the content of the files named above and use it directly, "
                    "including for locating course outcomes):\n\n"
                    + "\n\n".join(resolved_sections)
                )

        logger.info(f"Sending generation prompt for asset '{asset_type_name}' (course: {course_id}, prompt length: {len(prompt)} chars)")

        # AVAILABLE FIGURES — the figures resolved above are attached to the request
        # as vision input, and the menu below tells the model how to embed them.
        # Skipped for question-paper: its template already has a dedicated image
        # section driven by {{available_images}}, and two sets of instructions would
        # contradict each other.
        if figures and asset_type_name != "question-paper":
            menu_lines = []
            for f in figures:
                loc = f["resource_name"]
                if f.get("page") is not None:
                    loc += f" p.{f['page'] + 1}"
                menu_lines.append(f"- image_ref:{f['image_id']} | {loc} | caption: {f['caption'] or '(none)'}")
            prompt += (
                "\n\n---\n"
                "AVAILABLE FIGURES — The user may have attached images that can be used as figures "
                "in your output. The images are attached to this message so you can SEE them. Do not "
                "automatically embed figures unless they are relevant or the user explicitly asks you "
                "to include them.\n\n"
                "When a figure is relevant and adds meaningful value to the requested output, embed "
                "it using EXACTLY this markdown format — do NOT merely mention the file name in "
                "prose; the image itself must appear:\n"
                "![short caption](image_ref:<id>)\n\n"
                "User instructions take priority: If the user explicitly specifies which image to "
                "use, what it should show/illustrate, or where it should be placed, follow that "
                "instruction exactly. Do not move the figure to another location or substitute "
                "another image unless necessary.\n\n"
                "When the user does not specify a particular image or location, choose the most "
                "relevant available figure and place it where it adds the most value — on its own "
                "line in the relevant section, or inside the relevant table cell when the output is "
                "a table.\n\n"
                "Use ONLY the image ids listed below; never invent an id or an image URL, and never "
                "write a bare file name in place of the image.\n\n"
                "If no figure is relevant and the user has not requested one, do not include any "
                "image.\n\n"
                "Keep the image URL/reference format exactly as provided. Do not modify, replace, or "
                "convert the image_ref:<id> value.\n\n"
                + "\n".join(menu_lines)
            )

        if figures:
            logger.info(
                f"[figures] attached {len(figures)} figure(s) for '{asset_type_name}'; "
                f"{sum(1 for f in figures if f['data_uri'])} with visible image data"
            )

        print("\n\n===== FINAL PROMPT SENT TO LLM =====\n")
        print(prompt)
        print("\n===== END PROMPT =====\n")

        # Build the user message. With figures/PDFs, attach the real image pixels
        # (vision) and/or the PDF files alongside the prompt. No figures/PDFs -> plain
        # text (byte-identical to the previous behaviour).
        user_content = prompt
        _vision_figs = [f for f in figures if f.get("data_uri")]
        if _vision_figs or pdf_inputs:
            user_content = [{"type": "input_text", "text": prompt}]
            for f in _vision_figs:
                label = f"Figure image_ref:{f['image_id']}"
                if f["caption"]:
                    label += f" — {f['caption']}"
                user_content.append({"type": "input_text", "text": label})
                user_content.append({"type": "input_image", "image_url": f["data_uri"], "detail": "auto"})
            for p in pdf_inputs:
                user_content.append({"type": "input_file", "filename": p["filename"], "file_data": p["data_uri"]})

        # Stream run with proper error handling
        handler = AssetChatStreamHandler(label=f"Asset Generation: {asset_type_name}", task_id=task_id)
        stream_was_interrupted = False
        # Use temperature 0.3 for mark-scheme to ensure consistency
        temp = 0.3 if asset_type_name == "mark-scheme" else 1.0
        try:
            with client.responses.stream(
                model=settings.OPENAI_MODEL,
                input=[
                    {"role": "system", "content": systemPrompt},
                    {"role": "user", "content": user_content}
                ],
                temperature=temp
            ) as stream:
                for event in stream:
                    handler.handle(event)
        except Exception as stream_error:
            stream_was_interrupted = True
            logger.warning(f"Stream interrupted in task {task_id}, but continuing to retrieve response: {stream_error}")
            # Continue - we can still get the response from thread messages even if stream was interrupted

        # Get complete response from handler
        complete_response = handler.response_text.strip()
        logger.info(f"Received LLM response for task {task_id} ({len(complete_response)} chars)")

        # Fallback: if streaming returned nothing, retry with non-streaming call once
        if not complete_response:
            logger.warning(f"No response text received for task {task_id}. Retrying with non-streaming response.")
            try:
                response = client.responses.create(
                    model=settings.OPENAI_MODEL,
                    input=[
                        {"role": "system", "content": systemPrompt},
                        {"role": "user", "content": user_content}
                    ],
                    temperature=temp
                )
                complete_response = (response.output_text or "").strip()
            except Exception as retry_error:
                logger.error(f"Non-stream retry failed for task {task_id}: {retry_error}")

        # Turn valid image_ref:<id> links into absolute served-image URLs (and drop
        # any hallucinated ids) so figures render wherever this content is shown.
        if complete_response and "![" in complete_response:
            complete_response = _resolve_image_refs(complete_response, course_id, allowed_image_ids)

        if asset_type_name == "sprint-plan":
            if not complete_response:
                raise Exception("No sprint plan content returned from model")
            course_name = course.get("name", "")
            cover_table = (
                f"| Name of the Sprint | {course_name} |\n"
                f"|---|---|\n"
                f"| Sprint code | To be filled by Academic Operations |\n"
                f"| CoE Offering it | |\n"
                f"| Number of Credits | 4 |\n"
                f"| Credit Structure (Lecture:Tutorial:Practical:Self-study) | To be filled by Academic Operations |\n"
                f"| Total Hours | 72 |\n"
                f"| Number of Weeks in a Sprint | 3 |\n"
                f"| Total Course Marks | 200 |\n"
                f"| Pass Criteria | As per academic regulations |\n"
                f"| Attendance Criteria | As per academic regulations |\n"
            )
            complete_response = f"{cover_table}\n\n{complete_response}"

        if not complete_response:
            raise Exception("No response available from stream handler")

        # Mark task as completed with result
        result = {
            "response": complete_response,
            "response_id": handler.response_id
        }
        task_manager.mark_completed(task_id, result)
        logger.info(f"Completed background task {task_id} for asset '{asset_type_name}'")

    except Exception as e:
        error_msg = str(e)
        # Don't fail the task if it's just a connection interruption - response might still be available
        if "incomplete chunked read" in error_msg.lower() or "peer closed connection" in error_msg.lower():
            logger.warning(f"Connection interrupted in background task {task_id} for asset '{asset_type_name}': {error_msg}")
        
        logger.error(f"Exception in background task {task_id} for asset '{asset_type_name}': {error_msg}")
        task_manager.mark_failed(task_id, error_msg)

@router.post("/courses/{course_id}/asset_chat/{asset_type_name}", response_model=TaskResponse)
async def create_asset_chat(course_id: str, asset_type_name: str, request: AssetRequest, user_id: str = Depends(verify_token)
):
    """
    Create asset chat generation task (runs in background)
    Returns task_id immediately - use /tasks/{task_id} to check status
    """
    try:
        # Backwards compatibility: Convert old "lesson-plans" to "lecture"
        if asset_type_name == "lesson-plans":
            asset_type_name = "lecture"
        
        # Validate course exists
        course = get_course(course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Guard: selected PDFs are sent directly to the model, which limits how much
        # file content it accepts per request. Block clearly if the selection is too big.
        pdf_meta = get_resource_pdfs_meta_for_names(course_id, request.file_names)
        if len(pdf_meta) > _MAX_CHAT_PDFS:
            raise HTTPException(
                status_code=400,
                detail=f"You can use at most {_MAX_CHAT_PDFS} PDFs per chat (selected {len(pdf_meta)}). Please deselect some.",
            )
        total_bytes = sum(int(d.get("size_bytes") or 0) for d in pdf_meta)
        total_pages = sum(int(d.get("pages") or 0) for d in pdf_meta)
        if total_bytes > _MAX_CHAT_PDF_BYTES or total_pages > _MAX_CHAT_PDF_PAGES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Selected PDFs are too large to send to the model "
                    f"({total_bytes / (1024 * 1024):.1f} MB, {total_pages} pages). "
                    f"Limit is ~{_MAX_CHAT_PDF_BYTES // (1024 * 1024)} MB / {_MAX_CHAT_PDF_PAGES} pages — please deselect some."
                ),
            )

        # Create task with creation timestamp
        task_id = task_manager.create_task(
            task_type="asset_chat_create",
            metadata={
                "course_id": course_id,
                "asset_type_name": asset_type_name,
                "user_id": user_id,
                "file_count": len(request.file_names),
                "created_at": datetime.now().strftime("%d %B %Y %H:%M:%S")
            }
        )

        # Run detached from the request (see _generation_executor)
        _generation_executor.submit(
            _process_asset_chat_background,
            task_id,
            course_id,
            asset_type_name,
            request.file_names,
            request.course_description,
            user_id
        )

        return TaskResponse(
            task_id=task_id,
            status="pending",
            message=f"Asset generation task created for '{asset_type_name}'"
        )

    except Exception as e:
        logger.error(f"Exception in create_asset_chat for asset '{asset_type_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

def _process_continue_asset_chat_background(task_id: str, course_id: str, asset_name: str, previous_response_id: str, user_prompt: str, user_id: str):
    """Background task to process asset chat continuation using Responses API"""
    try:
        task_manager.mark_processing(task_id)
        logger.info(f"Starting background task {task_id} for continue asset '{asset_name}'")
        logger.info(f"Previous response ID: {previous_response_id}")
        
        course = get_course(course_id)
        if not course:
            task_manager.mark_failed(task_id, "Course not found")
            return

        # Get asset type to determine temperature
        asset = get_asset_by_course_id_and_asset_name(course_id, asset_name)
        asset_type = asset.get("asset_type", "") if asset else ""
        temp = 0.3 if asset_type == "mark-scheme" else 1.0

        # Create and stream the run. No file_search/vector store: the conversation
        # continues from previous_response_id, which already carries the selected
        # files (injected text + directly-attached Mongo PDFs) from the first turn.
        handler = AssetChatStreamHandler(label=f"Continue Asset Chat: {asset_name}", task_id=task_id)

        stream_kwargs = {
            "model": settings.OPENAI_MODEL,
            "input": [{"role": "user", "content": user_prompt}],
            "temperature": temp,
            "previous_response_id": previous_response_id,
        }

        with client.responses.stream(**stream_kwargs) as stream:
            for event in stream:
                handler.handle(event)

        complete_response = handler.response_text.strip()

        # Turn valid image_ref:<id> links into absolute served-image URLs (and drop
        # any hallucinated ids), same as the initial generation. On follow-up turns
        # the original file selection is unknown, so every image of the course is a
        # valid target — the model can only re-emit ids it was shown earlier anyway.
        if complete_response and "![" in complete_response:
            try:
                allowed_image_ids = set(get_resource_image_ids_for_course(course_id))
            except Exception as img_err:
                allowed_image_ids = set()
                logger.warning(f"[figures] course image lookup failed: {img_err}")
            complete_response = _resolve_image_refs(complete_response, course_id, allowed_image_ids)

        # Mark task as completed with result
        result = {
            "response": complete_response,
            "response_id": handler.response_id
        }
        task_manager.mark_completed(task_id, result)
        logger.info(f"Completed background task {task_id} for continue asset '{asset_name}'")

    except Exception as e:
        logger.error(f"Exception in background task {task_id} for continue asset '{asset_name}': {e}")
        task_manager.mark_failed(task_id, str(e))

@router.put("/courses/{course_id}/asset_chat/{asset_name}", response_model=TaskResponse)
async def continue_asset_chat(course_id: str, asset_name: str, response_id: str, request: AssetPromptRequest, user_id: str = Depends(verify_token)):
    """
    Continue asset chat conversation (runs in background)
    Returns task_id immediately - use /tasks/{task_id} to check status
    """
    try:
        # Validate course exists
        course = get_course(course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        # Create task
        task_id = task_manager.create_task(
            task_type="asset_chat_continue",
            metadata={
                "course_id": course_id,
                "asset_name": asset_name,
                "response_id": response_id,
                "user_id": user_id
            }
        )

        # Run detached from the request (see _generation_executor)
        _generation_executor.submit(
            _process_continue_asset_chat_background,
            task_id,
            course_id,
            asset_name,
            response_id,
            request.user_prompt,
            user_id
        )

        return TaskResponse(
            task_id=task_id,
            status="pending",
            message=f"Asset chat continuation task created for '{asset_name}'"
        )

    except Exception as e:
        logger.error(f"Exception in continue_asset_chat for asset '{asset_name}': {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/courses/{course_id}/assets", response_model=AssetCreateResponse)
def save_asset(course_id: str, asset_name: str, asset_type: str, request: AssetCreateRequest, user_id: str = Depends(verify_token)):
    # TODO: Make this a configuration for the app overall, add the remaining categories and asset types here
    category_map = {
        "brainstorm": "curriculum",
        "course-outcomes": "curriculum",
        "concept-plan": "curriculum",
        "modules": "curriculum",
        "sprint-plan": "curriculum",
        "sprint-structure": "curriculum",
        "sprint-plan-doc": "curriculum",  # legacy name of sprint-structure
        "lecture": "curriculum",
        "course-notes": "curriculum",
        "project": "assessments",
        "activity": "assessments",
        "quiz": "assessments",
        "question-paper": "assessments",
        "mark-scheme": "assessments",
        "mock-interview": "assessments",
    }
    # Default to a safe category so saving never fails due to unmapped type
    asset_category = category_map.get(asset_type, "content")
    # For generated assets that need exact content ordering, do not apply extra cleaning.
    # NOTE: clean_text temporarily disabled — will be restored later.
    cleaned_text = request.content
    # if asset_type in ["mark-scheme", "sprint-plan"]:
    #     cleaned_text = request.content
    # else:
    #     cleaned_text = clean_text(request.content)
    
    # Get user's display name for the asset
    user_display_name = get_user_display_name(user_id)
    if not user_display_name:
        user_display_name = "Unknown User"

    try:
        if asset_type == "sprint-plan":
            delete_asset_from_db(course_id, asset_name)
        # Use provided created_at from task metadata, or fall back to current time
        asset_created_at = request.created_at or datetime.now().strftime("%d %B %Y %H:%M:%S")
        create_asset(course_id, asset_name, asset_category, asset_type, cleaned_text, user_display_name, asset_created_at, user_id)
    except ValueError as e:
        # Duplicate asset name or other validation errors
        raise HTTPException(status_code=409, detail=str(e))
    return AssetCreateResponse(message=f"Asset '{asset_name}' created successfully")

@router.post("/courses/{course_id}/assets/pdf")
def generate_asset_pdf(
    course_id: str,
    request: TextToPdfRequest,
    user_id: str = Depends(verify_token),
):
    """Generate a PDF from provided text content and stream it back to the client."""
    try:
        course = get_course(course_id)
        if not course:
            raise HTTPException(status_code=404, detail="Course not found")

        content = request.content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="Content must not be empty")

        pdf_bytes = text_to_pdf(content)
        filename = request.filename or f"{course_id}-asset.pdf"

        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate PDF for course {course_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"PDF generation failed: {str(e)}")

@router.post("/courses/{course_id}/assets/docx")
def generate_asset_docx(
    course_id: str,
    request: TextToDocxRequest,
    user_id: str = Depends(verify_token),
):
    """Generate a DOCX from provided text content and stream it back to the client."""
    try:
        if not course_id:
            raise HTTPException(status_code=400, detail="Course ID is required")

        content = request.content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="Content must not be empty")

        docx_bytes = text_to_docx(content)
        filename = request.filename or f"{course_id}-asset.docx"

        return Response(
            content=docx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate DOCX for course {course_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"DOCX generation failed: {str(e)}")


@router.post("/courses/{course_id}/assets/xlsx")
def generate_asset_xlsx(
    course_id: str,
    request: TextToDocxRequest,
    user_id: str = Depends(verify_token),
):
    """Generate an Excel workbook from provided text content and stream it back to the client."""
    try:
        if not course_id:
            raise HTTPException(status_code=400, detail="Course ID is required")

        content = request.content.strip()
        if not content:
            raise HTTPException(status_code=400, detail="Content must not be empty")

        filename = request.filename or f"{course_id}-asset.xlsx"
        sheet_title = re.sub(r"\.xlsx$", "", filename, flags=re.IGNORECASE)
        xlsx_bytes = text_to_xlsx(content, sheet_title=sheet_title)

        return Response(
            content=xlsx_bytes,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate XLSX for course {course_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"XLSX generation failed: {str(e)}")


@router.get("/courses/{course_id}/assets", response_model=AssetListResponse)
def get_assets(course_id: str, user_id: str = Depends(verify_token)):
    assets = get_assets_by_course_id(course_id)
    return AssetListResponse(assets=assets)

@router.get("/courses/{course_id}/assets/{asset_name}/view", response_model=AssetViewResponse)
def view_asset(course_id: str, asset_name: str, user_id: str = Depends(verify_token)):
    asset = get_asset_by_course_id_and_asset_name(course_id, asset_name)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return AssetViewResponse(
        asset_name=asset["asset_name"], 
        asset_type=asset["asset_type"], 
        asset_category=asset["asset_category"], 
        asset_content=asset["asset_content"], 
        asset_last_updated_by=asset["asset_last_updated_by"], 
        asset_last_updated_at=asset["asset_last_updated_at"],
        created_by_user_id=asset.get("created_by_user_id")
    )

@router.post("/courses/{course_id}/assets/image", response_model=ImageResponse)
def create_image(course_id: str, asset_type_name: str, user_id: str = Depends(verify_token)):
    course = get_course(course_id)
    if not course:
        raise HTTPException(status_code=404, detail="Course not found")

    input_variables = construct_input_variables(course, [])
    parser = PromptParser()
    prompt = parser.get_asset_prompt(asset_type_name, input_variables)

    image = client.images.generate(
        model="dall-e-3",
        prompt=prompt,
        n=1,
        size="1024x1024"
    )

    # Extract URL
    image_url = image.data[0].url

    return ImageResponse(image_url=image_url)

# NOTE: knowledge-base images are served by GET /courses/{id}/images/{image_id}
# in routes/resources.py, which owns the resource_images collection and the
# res_<slug> image id scheme used throughout the figure pipeline.

#delete asset
@router.delete("/courses/{course_id}/assets/{asset_name}", response_model=AssetCreateResponse)
def delete_asset(course_id: str, asset_name: str, user_id: str = Depends(verify_token)):
    try:
        # Check if asset exists
        asset = get_asset_by_course_id_and_asset_name(course_id, asset_name)
        if not asset:
            raise HTTPException(status_code=404, detail="Asset not found")
        
        # Delete asset using the dedicated function
        delete_asset_from_db(course_id, asset_name)
        
        return AssetCreateResponse(message=f"Asset '{asset_name}' deleted successfully")
    except Exception as e:
        logger.error(f"Error deleting asset '{asset_name}': {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/courses/{course_id}/assets/{asset_name}/save-as-resource", response_model=AssetCreateResponse)
def save_asset_as_resource(course_id: str, asset_name: str, request: AssetCreateRequest, user_id: str = Depends(verify_token)):
    """Save an existing asset as a resource so it can be viewed in the resource view modal"""
    try:
        
        # 2. Get the content from the frontend request
        content = request.content
        logger.info(f"Received content for asset '{asset_name}': {content[:100] if content else 'None'}...")
        if not content:
            raise HTTPException(status_code=404, detail="Content not provided")

        
        # 5. Save the content as a resource in Mongo. That is the knowledge base:
        # generation reads this content back via _resolve_selected_text_sections.
        # The frontend dedupes against its (possibly stale) resource list, so pick a
        # unique name server-side too; create_resource never overwrites, and a False
        # return means another save took the name in between — retry with a fresh list.
        logger.info(f"Saving resource: {asset_name} with content length: {len(content)}")
        resource_name = None
        for _ in range(3):
            used = {r.get("resource_name") for r in (get_resources_by_course_id(course_id) or []) if r.get("resource_name")}
            candidate = ensure_unique_name(asset_name, used)
            if create_resource(course_id, candidate, content):
                resource_name = candidate
                break
        if not resource_name:
            raise HTTPException(status_code=409, detail=f"Could not save '{asset_name}' as a resource: the name is already in use. Please try again.")
        logger.info(f"Resource saved successfully: {resource_name}")

        # Also store a rendered PDF (same renderer as the PDF download, so tables,
        # math and embedded course images are kept) so that selecting this resource
        # sends the PDF directly to the model, like an uploaded PDF. Best-effort: if
        # rendering fails, the text saved above is still injected as a fallback.
        try:
            pdf_bytes = text_to_pdf(content)
            if len(pdf_bytes) <= _MAX_PDF_BYTES:
                try:
                    pages = len(PdfReader(io.BytesIO(pdf_bytes)).pages)
                except Exception:
                    pages = 0
                save_resource_pdf(course_id, resource_name, pdf_bytes, len(pdf_bytes), pages)
                logger.info(f"[pdf] stored rendered PDF for resource '{resource_name}' ({len(pdf_bytes)} bytes, {pages} pages)")
            else:
                logger.warning(f"[pdf] rendered PDF for '{resource_name}' exceeds {_MAX_PDF_BYTES} bytes; text only")
        except Exception as pdf_err:
            logger.warning(f"[pdf] could not render PDF for resource '{resource_name}'; text only: {pdf_err}")

        return AssetCreateResponse(message=f"Asset '{asset_name}' saved as resource '{resource_name}' successfully")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error saving asset '{asset_name}' as resource: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# Task Status Endpoints
@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str, user_id: str = Depends(verify_token)):
    """
    Get the status of a background task
    Use this to poll for task completion after starting an async asset generation
    """
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return TaskStatusResponse(
        task_id=task.task_id,
        status=task.status.value,
        result=task.result,
        error=task.error,
        metadata=task.metadata,
        partial=task.partial
    )

@router.delete("/tasks/{task_id}")
async def cancel_task(task_id: str, user_id: str = Depends(verify_token)):
    """
    Cancel a pending or running task
    Note: Tasks already in progress will complete but results won't be stored
    """
    task = task_manager.get_task(task_id)
    
    if not task:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    if task.status in [TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        return {"message": f"Task {task_id} already finished with status: {task.status.value}"}
    
    task_manager.mark_cancelled(task_id)
    return {"message": f"Task {task_id} cancelled"}
