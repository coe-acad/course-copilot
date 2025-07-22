import json
from pybars3 import Compiler
import os
from ..services.storage_course import storage_service

class PromptParser:
    def __init__(self):
        self.compiler = Compiler()

    def _load_template_json(self, template_file_path):
        if not os.path.exists(template_file_path):
            raise FileNotFoundError(f"Prompt template file not found: {template_file_path}")
        with open(template_file_path, 'r', encoding='utf-8') as file:
            return json.load(file)

    def render_prompt(self, template_file_path, input_variables):
        """
        Loads the prompt template JSON from the given file path, validates required variables, and renders the prompt.
        Args:
            template_file_path: Full path to the template JSON file
            input_variables: dict of variable values
        Returns:
            Rendered prompt string
        """
        data = self._load_template_json(template_file_path)
        prompt_template = data.get('prompt')
        required_vars = data.get('required_input_variables', [])
        optional_vars = data.get('optional_input_variables', [])

        # Validate required variables
        missing = [var for var in required_vars if var not in input_variables]
        if missing:
            raise ValueError(f"Missing required input variables for prompt: {missing}")

        # Only pass required + optional variables
        context = {
            variable_name: variable_value
            for variable_name, variable_value in input_variables.items()
            if variable_name in required_vars or variable_name in optional_vars
        }
        template = self.compiler.compile(prompt_template)
        return ''.join(template(context))

    def _get_input_variables(self, course_id, user_id):
        """
        Gathers all necessary input variables for a prompt.
        """
        course = storage_service.get_course(course_id, user_id)
        if not course:
            raise ValueError("Course not found")

        settings = course.get("settings", {})
        
        # Gather file names
        all_resources = storage_service.get_resources(course_id, user_id=user_id)
        checked_in_files = [
            r.get("title", r.get("fileName", "Unknown file"))
            for r in all_resources
            if r.get("status") == "checked_in"
        ]

        input_variables = {
            "course_name": course.get("name"),
            "course_level": settings.get("course_level"),
            "study_area": settings.get("study_area"),
            "pedagogical_components": settings.get("pedagogical_components"),
            "ask_clarifying_questions": settings.get("ask_clarifying_questions"),
            "file_names": ", ".join(checked_in_files) if checked_in_files else "No files checked in"
        }
        return input_variables

    def get_asset_prompt(self, asset_name, course_id, user_id):
        """
        Constructs a full prompt by combining system and asset templates.
        """
        input_variables = self._get_input_variables(course_id, user_id)
        
        # Define paths for the prompt templates
        base_prompt_path = os.path.join(os.path.dirname(__file__), '..', 'prompts')
        system_context_path = os.path.join(base_prompt_path, 'system', 'overall_context.json')
        system_settings_path = os.path.join(base_prompt_path, 'system', 'settings.json')
        asset_prompt_path = os.path.join(base_prompt_path, 'asset', f'{asset_name}.json')

        # Render each part of the prompt
        system_context_prompt = self.render_prompt(system_context_path, input_variables)
        system_settings_prompt = self.render_prompt(system_settings_path, input_variables)
        asset_prompt = self.render_prompt(asset_prompt_path, input_variables)

        # Combine the prompts
        final_prompt = f"{system_context_prompt}\n\n{system_settings_prompt}\n\n{asset_prompt}"
        return final_prompt