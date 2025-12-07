import inspect
import json
from dataclasses import dataclass
from typing import (
    Any,
    Callable,
    Optional,
    Tuple,
    Type,
    get_args, Dict,
)

from openai.types.chat.chat_completion_function_tool_param import (
    ChatCompletionFunctionToolParam,
)
from openai.types.shared_params.function_definition import FunctionDefinition
from pydantic import BaseModel, Field
from pydantic.config import ConfigDict
from pydantic.json_schema import DEFAULT_REF_TEMPLATE

from lang3s.utils.async_helper import run_sync


@dataclass
class LLMTool:
    name: str
    is_async: bool
    schema: ChatCompletionFunctionToolParam
    arg_validator: Type[BaseModel]
    function: Callable[..., Any]


@dataclass
class ToolCall:
    name: str
    tool_call_id: str
    arguments: Dict[str, Any]
    arguments_type: Type[BaseModel]
    is_async: bool
    function: Callable[..., Any]

    def invoke(self, max_retries: int = 3) -> Dict[str, Any]:
        return run_sync(self.async_invoke(max_retries=max_retries))

    async def async_invoke(self, max_retries: int = 3) -> Dict[str, Any]:
        last_exception = None
        for _ in range(max_retries):
            try:

                try:
                    arguments = self.arguments_type.model_validate(self.arguments)
                except Exception as e:
                    raise RuntimeError(e)

                if self.is_async:
                    raw_result = await self.function(**arguments.model_dump())
                else:
                    raw_result = self.function(**arguments.model_dump())

                if isinstance(raw_result, BaseModel):
                    content = raw_result.model_dump_json()
                elif isinstance(raw_result, (dict, list)):
                    content = json.dumps(raw_result)
                elif isinstance(raw_result, (int, float, bool)):
                    content = json.dumps({"result": raw_result})
                elif isinstance(raw_result, str):
                    content = json.dumps({"result": raw_result})
                elif raw_result is None:
                    content = json.dumps({"result": None})
                else:
                    content = json.dumps({"result": str(raw_result)})

                return {"role": "tool",
                        "name": self.name,
                        "tool_call_id": self.tool_call_id,
                        "content": content}
            except Exception as e:
                last_exception = e
                continue

        raise RuntimeError(
            f"Tool '{self.name}' failed after {max_retries} attempts.\n"
            f"Arguments: {self.arguments}\n"
            f"Error: {last_exception}"
        )


class Desc(str):
    """
    A simple class to hold parameter description within typing.Annotated.
    Pydantic will automatically pick this up.
    """
    pass


def tool(name: Optional[str] = None,
         description: Optional[str] = None):
    def to_json_schema(func: Callable[..., Any],
                       func_name: str,
                       func_description: str) -> Tuple[Type[BaseModel], ChatCompletionFunctionToolParam]:
        """
        Converts a Python function with type hints (including typing.Annotated)
        into a JSON Schema by dynamically creating a Pydantic Model correctly.
        """

        sig = inspect.signature(func)
        field_definitions = {}  # Stores {name: FieldInfo}
        annotations = {}  # Stores {name: base_type}

        for name, param in sig.parameters.items():
            param_annotation = param.annotation
            description = None

            if get_args(param_annotation) and get_args(param_annotation)[0] is not param_annotation:
                base_type, *metadata = get_args(param_annotation)

                for item in metadata:
                    if isinstance(item, Desc) or (isinstance(item, str) and not item.startswith(('ge=', 'le='))):
                        description = str(item)
                        break
            else:
                raise ValueError("Arguments must be annotated with typing.Annotated")

            # 2. Determine the Field definition kwargs
            field_kwargs = {}

            if param.default is param.empty:
                field_kwargs['default'] = ...
            else:
                field_kwargs['default'] = param.default

            if description:
                field_kwargs['description'] = description

            annotations[name] = base_type
            field_definitions[name] = Field(**field_kwargs)

        ParamModel = type(
            'ParamModel',
            (BaseModel,),
            {'__annotations__': annotations,
             **field_definitions,
             "model_config": ConfigDict(extra="ignore")
             },
        )

        # Generate the JSON Schema
        param_schema = ParamModel.model_json_schema(ref_template=DEFAULT_REF_TEMPLATE)  # type:ignore

        # Clean up and structure the schema for function calling
        properties_schema = {
            "type": "object",
            "properties": param_schema.get("properties", {}),
            "required": param_schema.get("required", [])
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
