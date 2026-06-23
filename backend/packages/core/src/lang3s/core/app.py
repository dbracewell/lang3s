import argparse
import json
import sys
import traceback
import types
from typing import (
    Any,
    ClassVar,
    Dict,
    List,
    Optional,
    Type,
    Union,
    get_args,
    get_origin,
)

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from lang3s.core.logger import get_logger


def _unwrap_optional(annotation):
    """
    Turns Optional[T] / Union[T, NoneType] / (T | None) into T.
    Otherwise returns annotation unchanged.
    """
    origin = get_origin(annotation)
    if origin in (Union, types.UnionType, Optional):
        args = get_args(annotation)
        non_none = [a for a in args if a is not type(None)]
        if len(non_none) == 1:
            return non_none[0]  # return T
    return annotation


class Application(BaseModel):
    """
    Base Application class with:

    - Automatic argparse generation from Pydantic fields
    - Docstring → help/description
    - YAML config loading (merged with CLI)
    - Subcommands

    Subclasses should define typed fields and implement `.run()`.
    """

    model_config: ClassVar[ConfigDict] = ConfigDict(
        extra="allow",
        validate_assignment=True,
        arbitrary_types_allowed=True,
    )

    extra_args: List[str] = Field(
        default_factory=list,
        description="Additional args not consumed by the parser",
    )
    config_file: Optional[str] = Field(
        default=None,
        description="YAML config file to load settings from",
    )

    # Non-field class-level metadata (must be ClassVar so Pydantic doesn't
    # treat them as model fields and strip them off the class)
    subcommands: ClassVar[Dict[str, Type["Application"]]] = {}

    def run(self) -> Any:
        raise NotImplementedError("Subclasses must implement .run()")

    @classmethod
    def _load_yaml(cls, path: Optional[str]) -> Dict[str, Any]:
        if not path:
            return {}
        try:
            with open(path, "r") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            print(f"[WARN] Config file not found: {path}")
            return {}
        except Exception as e:
            print(f"[WARN] Failed to load YAML {path}: {e}")
            return {}

    @classmethod
    def _merge_config(
        cls,
        yaml_cfg: Dict[str, Any],
        cli_cfg: Dict[str, Any],
    ) -> Dict[str, Any]:
        merged = dict(yaml_cfg)
        merged.update({k: v for k, v in cli_cfg.items() if v is not None})
        return merged

    @classmethod
    def _add_arg(cls, parser: argparse.ArgumentParser, name: str, field: Any) -> None:
        # Skip internal fields in CLI
        if name in ("extra_args",):
            return

        help_text = field.description or ""
        dashed = f"--{name.replace('_', '-')}"
        underscored = f"--{name}"

        annotation = _unwrap_optional(field.annotation)
        default = field.default

        examples = field.examples or []
        if "ignore" in examples:
            return

        origin = get_origin(annotation)
        args = get_args(annotation)

        # bool → --flag / --no-flag
        if annotation is bool:
            group = parser.add_mutually_exclusive_group(required=False)
            group.add_argument(
                f"--no-{name.replace('_', '-')}",
                dest=name,
                action="store_false",
                help=f"Disable {name}",
            )
            group.add_argument(
                dashed,
                underscored,
                dest=name,
                action="store_true",
                help=help_text or f"Enable {name}",
            )

            parser.set_defaults(**{name: default})
            return

        # Enum
        if hasattr(annotation, "__members__"):
            parser.add_argument(
                dashed,
                underscored,
                type=str,
                choices=list(annotation.__members__.keys()),
                default=default,
                help=help_text,
            )
            return

        # list[T]
        if origin in (list, List):
            inner_type = args[0] if args else str

            def parse_list(value):
                if value is None:
                    return None if field.default is None else field.default
                if isinstance(value, list):
                    return [inner_type(v) for v in value]
                if (
                    isinstance(value, str)
                    and value.startswith("[")
                    and value.endswith("]")
                ):
                    try:
                        raw = json.loads(value)
                        return [inner_type(x) for x in raw]
                    except Exception:
                        pass
                return [inner_type(value)]

            parser.add_argument(
                dashed,
                underscored,
                nargs="*",
                type=str,
                default=default or [],
                help=help_text + " (multiple values allowed; supports JSON lists)",
                dest=name,
            )
            if not hasattr(cls, "_list_fields"):
                cls._list_fields = {}

            cls._list_fields[name] = parse_list
            return

        # primitives
        if annotation in (int, float, str):
            parser.add_argument(
                dashed,
                underscored,
                type=annotation,
                default=default,
                help=help_text,
            )
            return

        # fallback: just accept as string-ish
        parser.add_argument(
            dashed,
            underscored,
            default=default,
            help=help_text,
        )

    @classmethod
    def _add_arguments_to_parser(cls, parser: argparse.ArgumentParser) -> None:
        for name, field in cls.model_fields.items():
            cls._add_arg(parser, name, field)

        parser.add_argument(
            "extra_args",
            nargs=argparse.REMAINDER,
            help="Additional args passed through untouched.",
        )

    @classmethod
    def build_parser(cls) -> argparse.ArgumentParser:
        parser = argparse.ArgumentParser(
            prog=cls.__name__,
            description=(cls.__doc__ or "").strip() or None,
        )

        # Subcommands
        if cls.subcommands:
            subparsers = parser.add_subparsers(
                dest="subcommand",
                required=True,
            )

            for name, subcls in cls.subcommands.items():
                sub_help = ""
                if subcls.__doc__:
                    sub_help = subcls.__doc__.strip().split("\n")[0]

                sp = subparsers.add_parser(name, help=sub_help)
                subcls._add_arguments_to_parser(sp)

            return parser

        cls._add_arguments_to_parser(parser)

        return parser

    @classmethod
    def from_cli(cls) -> "Application":
        argv = sys.argv[1:]
        parser = cls.build_parser()
        parsed = parser.parse_args(argv)
        # parsed, leftover = parser.parse_known_args(argv)
        leftover = []
        data = vars(parsed)

        for i in range(len(leftover)):
            if leftover[i].startswith("--logger."):
                logger_name = leftover[i][len("--logger.") :]
                if "=" in logger_name:
                    parts = logger_name.split("=")
                    logger_name = parts[0].strip()
                    logger_value = parts[1].strip()
                else:
                    logger_value = leftover[i + 1]
                    i += 1
                get_logger(logger_name).setLevel(logger_value.upper().strip())

        # Subcommand handling
        if cls.subcommands:
            subcmd_name = data.pop("subcommand")
            subcls = cls.subcommands[subcmd_name]
            sub_parser = subcls.build_parser()
            sub_parsed = sub_parser.parse_args(argv[1:])  # skip the subcommand itself
            sub_data = vars(sub_parsed)

            extra_cli = sub_data.pop("extra_args", [])
            config_path = sub_data.get("config_file")

            yaml_cfg = subcls._load_yaml(config_path)
            merged = subcls._merge_config(yaml_cfg, sub_data)

            app = subcls(**merged)
            app.extra_args = extra_cli
            return app

        # No subcommands → normal case
        extra_cli = data.pop("extra_args", [])
        config_path = data.get("config_file")

        yaml_cfg = cls._load_yaml(config_path)
        merged = cls._merge_config(yaml_cfg, data)

        if hasattr(cls, "_list_fields"):
            for field_name, parser_fn in cls._list_fields.items():
                if field_name in data:
                    data[field_name] = parser_fn(data[field_name])

        try:
            app = cls(**merged)
            app.extra_args = extra_cli
            return app
        except ValidationError:
            parser.print_help()
            traceback.print_exc()
            exit(1)
