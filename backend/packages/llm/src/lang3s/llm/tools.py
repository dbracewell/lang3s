import inspect
from typing import (
    Annotated,
    Any,
    Callable,
    Optional,
    Tuple,
    Type,
    get_args,
    get_origin,
    get_type_hints,
)

from openai.types.chat.chat_completion_function_tool_param import (
    ChatCompletionFunctionToolParam,
)
from openai.types.shared_params.function_definition import FunctionDefinition
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from pydantic.json_schema import DEFAULT_REF_TEMPLATE

from lang3s.llm.typedefs import ArgDesc, LLMTool


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
):
    def to_json_schema(
        func: Callable[..., Any],
        func_name: str,
        func_description: str,
    ) -> Tuple[Type[BaseModel], ChatCompletionFunctionToolParam]:
        """
        Converts a Python function with type hints (including typing.Annotated)
        into a JSON Schema by dynamically creating a Pydantic Model correctly.
        """

        sig = inspect.signature(func)
        type_hints = get_type_hints(func, include_extras=True)
        field_definitions = {}  # Stores {name: FieldInfo}
        annotations = {}  # Stores {name: base_type}

        for (param_name, param_annotation), param in zip(
            type_hints.items(),
            sig.parameters.values(),
        ):
            parameter_description = None

            if get_origin(param_annotation) is not Annotated:
                raise ValueError("Arguments must be annotated with typing.Annotated")

            base_type, *metadata = get_args(param_annotation)
            for item in metadata:
                if isinstance(item, ArgDesc):
                    parameter_description = str(item)
                    break

            field_kwargs = {}

            if param.default is param.empty:
                field_kwargs["default"] = ...
            else:
                field_kwargs["default"] = param.default

            if description:
                field_kwargs["description"] = parameter_description

            annotations[param_name] = base_type
            field_definitions[param_name] = Field(**field_kwargs)

        ParamModel = type(
            "ParamModel",
            (BaseModel,),
            {
                "__annotations__": annotations,
                **field_definitions,
                "model_config": ConfigDict(extra="ignore"),
            },
        )

        # Generate the JSON Schema
        param_schema = ParamModel.model_json_schema(ref_template=DEFAULT_REF_TEMPLATE)  # type:ignore

        # Clean up and structure the schema for function calling
        properties_schema = {
            "type": "object",
            "properties": param_schema.get("properties", {}),
            "required": param_schema.get("required", []),
        }

        if "$defs" in param_schema:
            properties_schema["$defs"] = param_schema["$defs"]

        properties_schema["additionalProperties"] = False
        function_schema = ChatCompletionFunctionToolParam(
            type="function",
            function=FunctionDefinition(
                name=func_name,
                description=func_description,
                strict=True,
                parameters=properties_schema,
            ),
        )

        return ParamModel, function_schema  # type: ignore

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        tool_name = name or func.__name__
        is_async = inspect.iscoroutinefunction(func)
        tool_desc = description or (inspect.getdoc(func) or "").strip()
        arg_validator, schema = to_json_schema(func, tool_name, tool_desc)
        wrapper.tool = LLMTool(
            name=tool_name,
            arg_validator=arg_validator,
            is_async=is_async,
            schema=schema,
            function=func,
        )
        return wrapper

    return decorator
