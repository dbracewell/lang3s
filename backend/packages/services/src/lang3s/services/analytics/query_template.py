from pathlib import Path

from jinja2 import Environment, FileSystemLoader, Template

from lang3s.core.typing_extras import SingletonMeta


class QueryTemplateEngine(metaclass=SingletonMeta):
    def __init__(self):
        self.jinja_env = Environment(
            loader=FileSystemLoader(Path(__file__).parent / "sql"),
            autoescape=False,
        )

    def get(self, template_name: str) -> Template:
        return self.jinja_env.get_template(template_name)

    def render(self, template_name: str, **kwargs) -> str:
        template = self.jinja_env.get_template(template_name)
        return template.render(**kwargs)

    def prepare_path_params(self, input_values: list[str]) -> list[str]:
        """
        Transforms a list of paths into the parameter list required by the
        match_paths SQL macro.

        Input:  ['ALL.Entity', 'Topic.Science']
        Output: ['ALL.Entity', 'ALL.Entity.%', 'Topic.Science', 'Topic.Science.%']
        """
        params = []
        for val in input_values:
            params.append(val)  # For = ?
            params.append(f"{val}.%")  # For LIKE ?
        return params


template_engine = QueryTemplateEngine()
