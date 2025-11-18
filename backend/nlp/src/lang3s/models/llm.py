import inspect
import logging
from dataclasses import dataclass
from typing import (
    Any,
    Awaitable,
    Callable,
    Dict,
    Iterable,
    List,
    Literal,
    Optional,
    Tuple,
    Type,
    TypedDict,
    Union,
    cast,
)

import openai
from openai.types.chat.chat_completion_function_tool_param import (
    ChatCompletionFunctionToolParam,
)
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.chat_completion_tool_union_param import (
    ChatCompletionToolUnionParam,
)
from openai.types.shared_params.function_definition import FunctionDefinition
from openai.types.shared_params.response_format_json_schema import (
    ResponseFormatJSONSchema,
    JSONSchema,
)
from pydantic import BaseModel

from lang3s import config

logger = logging.getLogger(__name__)


class Message(TypedDict):
    role: Literal["assistant", "user", "system"]
    content: str


def make_message(
    role: Literal["assistant", "user", "system", "tool"],
    content: Optional[str] = None,
    *,
    tool_call_id: Optional[str] = None,
    name: Optional[str] = None,
) -> ChatCompletionMessageParam:
    """
    Helper to build messages compatible with openai.types chat params.
    NOTE:
      - tool messages MUST NOT have a 'name' field
      - assistant messages with tool_calls have 'tool_calls' instead of content
    """
    base: Dict[str, Any] = {"role": role}
    if content is not None:
        base["content"] = content
    if role == "tool":
        if tool_call_id is None:
            raise ValueError("tool_call_id is required for tool messages")
        base["tool_call_id"] = tool_call_id
    else:
        if name is not None:
            base["name"] = name
    return cast(ChatCompletionMessageParam, cast(object, base))


def json_response_format(name: str, schema: Dict[str, Any]) -> ResponseFormatJSONSchema:
    """
    Build a JSON-schema response_format object for structured output.
    """
    schema.setdefault("additionalProperties", False)
    return ResponseFormatJSONSchema(
        type="json_schema",
        json_schema=JSONSchema(name=name, schema=schema),
    )


@dataclass
class RegisteredTool:
    name: str
    description: str
    args_model: Type[BaseModel]
    func: Union[Callable[..., Any], Callable[..., Awaitable[Any]]]
    is_async: bool
    result_model: Optional[Type[BaseModel]] = None


def generate_tool_schema_description(tools: Dict[str, "RegisteredTool"]) -> str:
    """
    Generate a natural-language description of all tools and their argument schemas.
    This is inserted into the PlanStep prompt to teach the LLM what parameters
    each tool requires and how to format them.
    """
    lines = ["Tool Argument Specifications:"]

    for tool_name, tool in tools.items():
        lines.append(f"\n- {tool_name}:")
        lines.append(f"    Description: {tool.description}")

        # Extract arg model schema if tool.args_model exists
        if hasattr(tool, "args_model") and tool.args_model is not None:
            schema = tool.args_model.model_json_schema()
            props = schema.get("properties", {})
            required = set(schema.get("required", []))

            lines.append("    Arguments:")
            for arg_name, arg_schema in props.items():
                arg_type = arg_schema.get("type", "any")
                arg_desc = arg_schema.get("description", "No description provided.")
                req = "required" if arg_name in required else "optional"

                lines.append(
                    f"      - {arg_name} ({arg_type}, {req}): {arg_desc}"
                )

            # Example JSON structure
            example_args = {
                name: f"<{name}_value>"
                for name in props.keys()
            }
            lines.append("    Example args:")
            lines.append(f"      {example_args}")
        else:
            # Fallback when no args_model exists
            lines.append("    (No argument schema available)")

    return "\n".join(lines)


class ToolRegistry:
    """
    Lightweight tool orchestration registry. Handles:
      - Tool registration
      - Conversion to OpenAI tool definitions
      - Lookup by name
    """

    def __init__(self) -> None:
        self._tools: Dict[str, RegisteredTool] = {}

    def generate_schema(self, tools: List[str]) -> str:
        temp = {}
        for tool_name in tools:
            if tool_name in self._tools:
                temp[tool_name] = self._tools[tool_name]
        return generate_tool_schema_description(temp)

    def register(self, tool: RegisteredTool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def get(self, name: str) -> RegisteredTool:
        try:
            return self._tools[name]
        except KeyError:
            raise RuntimeError(f"Unknown tool requested by model: {name!r}")

    def all(self) -> List[RegisteredTool]:
        return list(self._tools.values())

    def names(self) -> List[str]:
        return list(self._tools.keys())

    def select(self, names: Optional[Iterable[str]]) -> List[RegisteredTool]:
        if names is None:
            return self.all()
        return [self.get(n) for n in names]

    # Decorator:
    def tool(
        self,
        *,
        args_model: Type[BaseModel],
        result_model: Optional[Type[BaseModel]] = None,
        description: str = "",
        name: Optional[str] = None,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        """
        Decorator to register a function as a tool with Pydantic-based argument schema.

        Example:
            class AddArgs(BaseModel):
                a: int
                b: int

            class AddResult(BaseModel):
                result: int

            registry = ToolRegistry()

            @registry.tool(args_model=AddArgs, result_model=AddResult, description="Add two ints")
            def add(a: int, b: int) -> dict:
                return {"result": a + b}
        """

        def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
            tool_name = name or func.__name__
            is_async = inspect.iscoroutinefunction(func)
            tool_desc = description or (func.__doc__ or "").strip()

            self.register(
                RegisteredTool(
                    name=tool_name,
                    description=tool_desc,
                    args_model=args_model,
                    func=func,
                    is_async=is_async,
                    result_model=result_model,
                )
            )
            return func

        return decorator


def tool_to_openai_definition(tool: RegisteredTool) -> ChatCompletionToolUnionParam:
    """
    Convert a RegisteredTool into an OpenAI function tool definition.
    """
    params_schema = tool.args_model.model_json_schema()
    params_schema.setdefault("additionalProperties", False)

    return ChatCompletionFunctionToolParam(
        type="function",
        function=FunctionDefinition(
            name=tool.name,
            description=tool.description,
            strict=True,
            parameters=params_schema,
        ),
    )


class LLMOrchestrator:
    """
    A single-round executor:
        - If tools are provided → model may call tools
        - If response_model is provided → model must output structured JSON
        - Otherwise → plain generation
    No loops. No phases. No recursion.
    The Agent is responsible for orchestration.
    """

    def __init__(self, client: openai.OpenAI, async_client: openai.AsyncOpenAI, model: str, tool_registry=None):
        self.client = client
        self.async_client = async_client
        self.model = model
        self.registry: ToolRegistry = tool_registry or ToolRegistry()

    def chat(
        self,
        messages: List[dict],
        *,
        tool_names: Optional[List[str]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        force_tool_call: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
        }

        # ---------- Tools ----------
        if tool_names:
            tools = [self.registry.get(name) for name in tool_names]
            payload["tools"] = [tool_to_openai_definition(t) for t in tools]
            payload["tool_choice"] = "required" if force_tool_call else "auto"

        # ---------- Structured Output ----------
        if response_model is not None:
            payload["response_format"] = json_response_format(
                response_model.__name__,
                response_model.model_json_schema(),
            )

        # ---------- Call model ----------
        response = self.client.chat.completions.create(**payload)
        msg = response.choices[0].message

        # Normalize
        return {
            "assistant_message": msg,
            "tool_calls": msg.tool_calls or [],
            "content": msg.content,
        }

    # --------- ASYNC version ---------
    async def achat(
        self,
        messages: List[Dict[str, Any]],
        *,
        tool_names: Optional[List[str]] = None,
        response_model: Optional[Type[BaseModel] | Tuple[str, Dict[str, Any]]] = None,
        force_tool_call: bool = False,
    ) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "reasoning_effort": "low",
        }

        if tool_names:
            tools = [self.registry.get(name) for name in tool_names]
            payload["tools"] = [tool_to_openai_definition(t) for t in tools]
            payload["tool_choice"] = "required" if force_tool_call else "auto"

        if response_model is not None:
            if isinstance(response_model, Tuple):
                print(response_model[0])
                print(response_model[1])
                payload["response_format"] = json_response_format(
                    response_model[0],
                    response_model[1],
                )
            else:
                payload["response_format"] = json_response_format(
                    response_model.__name__,
                    response_model.model_json_schema(),
                )

        response = await self.async_client.chat.completions.create(**payload)
        msg = response.choices[0].message

        return {
            "assistant_message": msg,
            "tool_calls": msg.tool_calls or [],
            "content": msg.content,
        }


sync_llm_client = openai.OpenAI(
    api_key=config.LLM_API_KEY,
    base_url=f"{config.LLM_HOST}/v1/",
)

async_llm_client = openai.AsyncOpenAI(
    api_key=config.LLM_API_KEY,
    base_url=f"{config.LLM_HOST}/v1/",
)

global_tool_registry = ToolRegistry()

orchestrator = LLMOrchestrator(
    client=sync_llm_client,
    async_client=async_llm_client,
    model=config.LLM_MODEL,
    tool_registry=global_tool_registry,
)
