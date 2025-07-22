import json
from pybars3 import Compiler
import os

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

    def render_get_prompt(self, template_file_path, input_variables):
        return ""