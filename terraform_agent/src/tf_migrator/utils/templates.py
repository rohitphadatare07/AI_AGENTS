"""Template rendering helpers for Terraform migration."""


def render_template(template: str, context: dict) -> str:
    """Render a simple template with context mapping."""
    return template.format(**context)
