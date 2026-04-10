from typing import Dict, List, Literal, Set, Type, Union, get_args, get_origin

from pydantic import BaseModel, Field


def get_type_name(annotation) -> str:
    if isinstance(annotation, type) and issubclass(annotation, BaseModel):
        return to_structured_format(annotation)

    origin = get_origin(annotation)
    args = get_args(annotation)

    if origin is Literal:
        return " | ".join(repr(a) for a in args)

    if origin is Union:
        return " | ".join(get_type_name(a) for a in args)

    if origin is not None:
        type_args = [get_type_name(a) for a in args]
        if origin in (list, set, List, Set):
            return f"{type_args[0]}[]"
        if origin in (dict, Dict):
            return f"{{[key: {type_args[0]}]: {type_args[1]}}}"

        name = getattr(origin, "__name__", str(origin))
        return f"{name}[{', '.join(type_args)}]"

    if hasattr(annotation, "__name__"):
        return annotation.__name__

    return str(annotation).replace("typing.", "")


def to_structured_format(model: Type[BaseModel]) -> str:
    fields = [
        f'"{name}": {get_type_name(field.annotation)}'
        for name, field in model.model_fields.items()
    ]
    return "{" + ", ".join(fields) + "}"
