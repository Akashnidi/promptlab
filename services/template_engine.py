from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from jinja2 import Environment, TemplateError, TemplateSyntaxError, meta


class TemplateEngine:
    def __init__(self):
        self.env = Environment()

    def extract_variables(self, template_text: str) -> List[str]:
        """Extract all undeclared variables from Jinja2 template AST."""
        if not template_text or not template_text.strip():
            return []
        try:
            ast = self.env.parse(template_text)
            vars_set = meta.find_undeclared_variables(ast)
            return sorted(list(vars_set))
        except (TemplateSyntaxError, TemplateError, Exception):
            return []

    def render(self, template_text: str, variables: Optional[Dict[str, Any]] = None) -> str:
        """Render template with provided variable dictionary."""
        if variables is None:
            variables = {}
        try:
            template = self.env.from_string(template_text)
            return template.render(**variables)
        except Exception as e:
            return f"[Template Render Error: {str(e)}]"

    def validate(self, template_text: str) -> Tuple[bool, str]:
        """Validate template syntax. Returns (True, '') or (False, error_msg)."""
        if not template_text:
            return True, ""
        try:
            self.env.parse(template_text)
            return True, ""
        except TemplateSyntaxError as e:
            return False, f"Line {e.lineno}: {e.message}"
        except Exception as e:
            return False, str(e)

    def load_from_file(self, filepath: str) -> Tuple[str, List[str]]:
        """Read template file and extract variables."""
        path = Path(filepath)
        if not path.exists():
            return "", []
        content = path.read_text(encoding="utf-8")
        variables = self.extract_variables(content)
        return content, variables
