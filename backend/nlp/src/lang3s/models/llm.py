import inspect
import json
import logging
from typing import Any, Callable, Dict, List, NamedTuple, Optional, Sequence, Type, TypedDict, Literal, TypeVar, cast

import openai
from openai.types.chat.chat_completion_function_tool_param import ChatCompletionFunctionToolParam
from openai.types.chat.chat_completion_message_function_tool_call import ChatCompletionMessageFunctionToolCall
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.chat_completion_tool_union_param import ChatCompletionToolUnionParam
from openai.types.shared_params.function_definition import FunctionDefinition
from openai.types.shared_params.response_format_json_schema import ResponseFormatJSONSchema, JSONSchema
from pydantic import BaseModel

from lang3s import config

T = TypeVar("T", bound=BaseModel)

MAX_ROUNDS = 10

logger = logging.getLogger(__name__)


class Message(TypedDict):
    role: Literal["assistant", "user", "system"]
    content: str


class ToolParam(NamedTuple):
    type: str
    name: str
    description: str
    required: bool


class Tool(NamedTuple):
    name: str
    function: Callable
    description: str
    params: List[ToolParam]


def message(role: str, content: Optional[str] = None,
            *, tool_call_id: Optional[str] = None,
            name: Optional[str] = None) -> ChatCompletionMessageParam:
    """
    Build a minimal dict that satisfies the `ChatCompletionMessageParam` type.
    The function keeps the API surface tiny – you only ever need role/content or
    the three tool‑specific fields.
    """
    base: Dict[str, Any] = {"role": role}
    if content is not None:
        base["content"] = content
    if tool_call_id is not None and name is not None:
        base.update({"name": name, "tool_call_id": tool_call_id})
    return cast(ChatCompletionMessageParam, cast(object, base))


def json_response_format(name: str, schema: Dict[str, Any]):
    return ResponseFormatJSONSchema(type="json_schema",
                                    json_schema=JSONSchema(name=name, schema=schema))


llm = openai.OpenAI(api_key=config.LLM_API_KEY, base_url=f"{config.LLM_HOST}/v1/")


def _generate_tool_definition(tools: Optional[List[Tool]] = None):
    tool_def: List[ChatCompletionToolUnionParam] = []
    for tool in tools or []:
        function_parameters = {"type": "object", "properties": {}, "required": []}
        for param in tool.params:
            function_parameters["properties"][param.name] = {
                "type": param.type,
                "description": param.description,
            }
            if param.required:
                function_parameters["required"].append(param.name)

        tool_def.append(ChatCompletionFunctionToolParam(type="function",
                                                        function=FunctionDefinition(strict=True,
                                                                                    name=tool.name,
                                                                                    description=tool.description,
                                                                                    parameters=function_parameters)))
    return tool_def


def tool(description: str, params: Dict[str, str]):
    def decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        # Extract function details for the tool schema
        tool_name = func.__name__
        tool_description = description

        parameters: List[ToolParam] = []

        signature = inspect.signature(func)
        for name, param in signature.parameters.items():
            param_type = "string"  # Default to string if no type annotation
            if param.annotation is not inspect.Parameter.empty:
                if param.annotation is str:
                    param_type = "string"
                elif param.annotation is int:
                    param_type = "number"  # OpenAI often uses 'number' for both int/float
                elif param.annotation is float:
                    param_type = "number"
                elif param.annotation is bool:
                    param_type = "boolean"
                # Add more type mappings as needed

            parameters.append(ToolParam(type=param_type,
                                        name=name,
                                        description=params.get(name, name),
                                        required=param.default is inspect.Parameter.empty
                                        ))

        wrapper.tool = Tool(name=tool_name,
                            function=func,
                            description=tool_description,
                            params=parameters)

        return wrapper

    return decorator


def generate_text(messages: Sequence[Message],
                  schema: Optional[Type[T]] = None,
                  tools: Optional[List[Tool]] = None) -> List[str]:
    round_counter = 0
    content = []
    chat_messages: List[ChatCompletionMessageParam] = [message(m["role"], m["content"]) for m in messages]

    while round_counter < MAX_ROUNDS:
        round_counter += 1

        payload: Dict[str, Any] = {
            "model": config.LLM_MODEL,
            "messages": chat_messages,
            "logprobs": True,
        }

        if tools is not None:
            payload["tools"] = _generate_tool_definition(tools)

        if schema is not None:
            payload["response_format"] = json_response_format(
                schema.__name__, schema.model_json_schema()
            )

        response = llm.chat.completions.create(**payload)
        choice = response.choices[0]
        msg = choice.message

        if msg.tool_calls:
            for call in cast(List[ChatCompletionMessageFunctionToolCall], msg.tool_calls):
                fn_name = call.function.name
                args: Dict[str, Any] = json.loads(call.function.arguments)

                tool = next((t for t in (tools or []) if t.name == fn_name), None)
                if not tool:
                    raise RuntimeError(f"Unknown tool requested: {fn_name}")

                result = tool.function(**args)
                logger.debug(f"Called {fn_name} with args {json.dumps(args)} and result of {json.dumps(result)}")
                chat_messages.append(
                    message(role=msg.role, content=msg.content)
                )
                chat_messages.append(
                    message(
                        role="tool",
                        tool_call_id=call.id,
                        name=fn_name,
                        content=json.dumps(result),
                    )
                )
            continue

        if msg.content:
            content.append(msg.content)
        break

    if round_counter >= MAX_ROUNDS and not content:
        raise RuntimeError("Exceeded maximum number of tool‑calling rounds")

    return content
