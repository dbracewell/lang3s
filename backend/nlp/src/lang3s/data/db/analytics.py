from pathlib import Path

import duckdb
from jinja2 import Environment, FileSystemLoader

from lang3s import config
from lang3s.data.db.filestore import FILE_STORE
from lang3s.utils.meta import SingletonMeta


class AnalyticsDB(metaclass=SingletonMeta):
    def __init__(self):
        self.jinja_env = Environment(
            loader=FileSystemLoader(Path(__file__).parent / "sql"),
            autoescape=False,
        )

        self.connection = duckdb.connect(FILE_STORE.get_analytics_db_path())
        self.connection.load_extension("json")
        self.connection.load_extension("fts")
        self.connection.load_extension("postgres")
        self.connection.execute("PRAGMA memory_limit='8GB';")
        postgres_url = f"dbname=lang3s user={config.DB_USER} password={config.DB_PASSWORD} host={config.DB_HOST} port={config.DB_PORT}"
        self.connection.execute(f"ATTACH '{postgres_url}' AS pg_db (TYPE POSTGRES)")
        self.connection.execute(self._get_query("duckdb_init.sql"))

    def build_annotation_stats(self):
        self.execute(self._get_query("annotation_stats_builder.sql.j2"))
        self.commit()

    def _get_query(self, template_name, **kwargs):
        template = self.jinja_env.get_template(template_name)
        return template.render(**kwargs)

    def get_template(self, template_name):
        return self.jinja_env.get_template(template_name)

    def run_query(self, query, parameters=None, **kwargs):
        return (
            self.connection.execute(self._get_query(query, **kwargs), parameters)
            .df()
            .to_dict(orient="records")
        )

    def execute(self, query, parameters=None):
        return self.connection.execute(query, parameters)

    def commit(self):
        self.connection.commit()

    def close(self):
        self.connection.close()

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


analytics_db: AnalyticsDB = None  # type:ignore


def init_db():
    global analytics_db
    analytics_db = AnalyticsDB()


def get_db():
    if analytics_db is None:
        print("No analytics db available")
        raise Exception("Database not initialized!")
    return analytics_db
