from logging import log
import logging
import re
import asyncio
import time
from io import BytesIO
from typing import Optional
from ..config.settings import settings
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from datetime import datetime
from ..utils.verify_token import verify_token
from ..utils.prompt_parser import PromptParser
from ..utils.openai_client import client
from ..utils.text_to_pdf import text_to_pdf
from ..utils.text_to_docx import text_to_docx
from ..utils.sprint_plan import build_sprint_plan
from ..services.mongo import get_course, create_asset, get_assets_by_course_id, get_asset_by_course_id_and_asset_name, delete_asset_from_db, create_resource, get_resource_by_course_id_and_resource_name, get_user_display_name, get_resource_image_by_id
from ..services.openai_service import clean_text, create_file, connect_file_to_vector_store
from ..services.mongo import get_course, create_asset, get_assets_by_course_id, get_asset_by_course_id_and_asset_name, delete_asset_from_db, create_resource, get_resource_by_course_id_and_resource_name, get_user_display_name, get_resource_images_for_names, get_resource_image_ids_for_course, get_resource_pdf, get_resource_pdfs_meta_for_names
from ..services.task_manager import task_manager, TaskStatus

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

class AssetChatStreamHandler:
    """Custom event handler for OpenAI Responses API streaming.
    
    Processes streaming events from the Responses API and accumulates
    the response text and response ID for later use.
    """
    def __init__(self, label: str = ""):
        self.response_text = ""
        self.response_id = None
        self.label = label

    def handle(self, event):
        if event.type == "response.created":
            self.response_id = event.response.id

        elif event.type == "response.output_text.delta":
            self.response_text += event.delta

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
            logger.info(f"[DEBUG] qp-extraction prompt_qp:\n{prompt_qp}")

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

        # # Prepare prompt
        # input_variables = construct_input_variables(course, file_names, course_description)
        # if sprint_plan_sources:
        #     input_variables.update(sprint_plan_sources)
        
        # # Add extracted_questions to input_variables if mark-scheme
        # if asset_type_name == "mark-scheme":
        #     input_variables["extracted_questions"] = extracted_questions
        
        # parser = PromptParser()
        # prompt = parser.get_asset_prompt(asset_type_name, input_variables)

        # Prepare prompt
        input_variables = construct_input_variables(
            course,
            file_names,
            course_description
        )

        if sprint_plan_sources:
            input_variables.update(sprint_plan_sources)


        # ---------------------------------------------------------
        # QUESTION PAPER: FIND SELECTED KNOWLEDGE-BASE IMAGES
        # ---------------------------------------------------------
        if asset_type_name == "question-paper":

            IMAGE_EXTENSIONS = (
                ".png",
                ".jpg",
                ".jpeg",
                ".webp"
            )

            available_images = []

            for fname in file_names:

                if not fname:
                    continue

                # Only process selected image files
                if not fname.lower().endswith(IMAGE_EXTENSIONS):
                    continue

                # Get the EXACT selected resource from MongoDB
                resource = get_resource_by_course_id_and_resource_name(
                    course_id,
                    fname
                )

                if not resource:
                    logger.warning(
                        f"[QP IMAGE] Selected image resource not found: {fname}"
                    )
                    continue

                # Get the MongoDB resource ID
                image_id = resource.get("_id")

                if not image_id:
                    logger.warning(
                        f"[QP IMAGE] Image resource has no _id: {fname}"
                    )
                    continue

                # Dynamic internal image path.
                # This matches the format expected by text_to_pdf.py:
                # /courses/{course_id}/images/{image_id}
                image_path = (
                    f"/courses/{course_id}/images/{str(image_id)}"
                )

                available_images.append(
                    {
                        "filename": fname,
                        "image_path": image_path
                    }
                )

                logger.info(
                    f"[QP IMAGE] Available image: "
                    f"{fname} -> {image_path}"
                )


            # Convert available images into text for the prompt
            if available_images:

                input_variables["available_images"] = "\n\n".join(
                    [
                        f"Filename: {image['filename']}\n"
                        f"Image Path: {image['image_path']}"
                        for image in available_images
                    ]
                )

            else:

                input_variables["available_images"] = (
                    "No image resources were selected."
                )


        # Add extracted_questions to input_variables if mark-scheme
        if asset_type_name == "mark-scheme":
            input_variables["extracted_questions"] = extracted_questions


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
        # AVAILABLE FIGURES — resolve extracted images for the selected files for
        # EVERY asset type, so the model can SEE them (vision, attached below) and
        # embed them where they add value. No images for the selection -> no-op and
        # the prompt / model call are unchanged.
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

        if figures:
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
        handler = AssetChatStreamHandler(label=f"Asset Generation: {asset_type_name}")
        stream_was_interrupted = False
        # Use temperature 0.3 for mark-scheme to ensure consistency
        temp = 0.3 if asset_type_name == "mark-scheme" else 1.0
        try:
            with client.responses.stream(
                model=settings.OPENAI_MODEL,
                input=[
                    {"role": "system", "content": systemPrompt},
                    {"role": "user", "content": prompt}
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
                        {"role": "user", "content": prompt}
                    ],
                    temperature=temp
                )
                complete_response = (response.output_text or "").strip()
            except Exception as retry_error:
                logger.error(f"Non-stream retry failed for task {task_id}: {retry_error}")

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
async def create_asset_chat(course_id: str, asset_type_name: str, request: AssetRequest, background_tasks: BackgroundTasks,user_id: str = Depends(verify_token)
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

        # Schedule background task
        background_tasks.add_task(
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
        handler = AssetChatStreamHandler(label=f"Continue Asset Chat: {asset_name}")

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
async def continue_asset_chat(course_id: str, asset_name: str, response_id: str, request: AssetPromptRequest, background_tasks: BackgroundTasks, user_id: str = Depends(verify_token)):
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

        # Schedule background task
        background_tasks.add_task(
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

# Serve a knowledge-base image stored in MongoDB resource_images.
# This is the endpoint the frontend uses to render images inside the
# question paper chat view via the /courses/{id}/images/{id} path.
@router.get("/courses/{course_id}/images/{image_id}")
def serve_resource_image(course_id: str, image_id: str):
    """Return raw image bytes for a knowledge-base image stored in MongoDB."""
    import base64
    img_doc = get_resource_image_by_id(course_id, image_id)
    if not img_doc:
        raise HTTPException(status_code=404, detail="Image not found")
    image_base64 = img_doc.get("image_base64", "")
    if not image_base64:
        raise HTTPException(status_code=404, detail="Image data missing")
    # Strip data URI prefix if present
    if "," in image_base64 and image_base64.startswith("data:"):
        image_base64 = image_base64.split(",", 1)[1]
    try:
        img_bytes = base64.b64decode(image_base64)
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decode image")
    mime = img_doc.get("image_mime", "image/png")
    return Response(content=img_bytes, media_type=mime)


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
        logger.info(f"Saving resource: {asset_name} with content length: {len(content)}")
        create_resource(course_id, asset_name, content)
        logger.info(f"Resource saved successfully: {asset_name}")

        return AssetCreateResponse(message=f"Asset '{asset_name}' saved as resource '{asset_name}' successfully")
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
        metadata=task.metadata
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