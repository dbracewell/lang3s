import asyncio
from functools import partial
import inspect
import json
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
    Sequence,
    Type,
    TypedDict,
    Union,
    cast,
)

import openai
from openai.types.chat.chat_completion_assistant_message_param import (
    ChatCompletionAssistantMessageParam,
)
from openai.types.chat.chat_completion_message_param import ChatCompletionMessageParam
from openai.types.chat.chat_completion_tool_message_param import (
    ChatCompletionToolMessageParam,
)
from openai.types.chat.chat_completion_tool_union_param import (
    ChatCompletionToolUnionParam,
)
from openai.types.chat.chat_completion_function_tool_param import (
    ChatCompletionFunctionToolParam,
)
from openai.types.chat.chat_completion_message_function_tool_call import (
    ChatCompletionMessageFunctionToolCall,
)
from openai.types.shared_params.function_definition import FunctionDefinition
from openai.types.shared_params.response_format_json_schema import (
    ResponseFormatJSONSchema,
    JSONSchema,
)
from pydantic import BaseModel, ValidationError

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


class ToolRegistry:
    """
    Lightweight tool orchestration registry. Handles:
      - Tool registration
      - Conversion to OpenAI tool definitions
      - Lookup by name
    """

    def __init__(self) -> None:
        self._tools: Dict[str, RegisteredTool] = {}

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
        self.registry = tool_registry or ToolRegistry()

    def chat(
        self,
        messages,
        *,
        tool_names: Optional[List[str]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        force_tool_call: bool = False,
    ):
        payload = {
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
        messages,
        *,
        tool_names: Optional[List[str]] = None,
        response_model: Optional[Type[BaseModel]] = None,
        force_tool_call: bool = False,
    ):
        payload = {
            "model": self.model,
            "messages": messages,
        }

        if tool_names:
            tools = [self.registry.get(name) for name in tool_names]
            payload["tools"] = [tool_to_openai_definition(t) for t in tools]
            payload["tool_choice"] = "required" if force_tool_call else "auto"

        if response_model is not None:
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


# class LLMOrchestrator:
#     """
#     High-level orchestrator for chat:
#       - multi-round tool calling
#       - Pydantic-based structured output
#       - sync + async APIs
#     """
#
#     def __init__(
#         self,
#         client: openai.OpenAI,
#         model: str,
#         tool_registry: Optional[ToolRegistry] = None,
#         max_rounds: int = 8,
#     ) -> None:
#         self.client = client
#         self.model = model
#         self.registry = tool_registry or ToolRegistry()
#         self.max_rounds = max_rounds
#
#     # ---------------- sync ----------------
#
#     def chat(
#         self,
#         messages: Sequence[Message],
#         *,
#         response_model: Optional[Type[BaseModel]] = None,
#         tool_names: Optional[Iterable[str]] = None,
#         force_tool_call: bool = False,
#     ) -> Union[List[str], List[BaseModel]]:
#         """
#         Synchronous high-level chat call.
#
#         - messages: list of {role, content}
#         - response_model: if provided, validate final assistant content as JSON into this Pydantic model
#         - tool_names: subset of tools to expose for this call (None = all registered tools)
#         - force_tool_call: if True, require the model to use tools on the first round
#         """
#         tools = self.registry.select(tool_names) if self.registry else []
#         chat_messages: List[ChatCompletionMessageParam] = [
#             make_message(m["role"], m["content"]) for m in messages
#         ]
#
#         round_counter = 0
#         results: List[Union[str, BaseModel]] = []
#
#         while round_counter < self.max_rounds:
#             round_counter += 1
#
#             payload: Dict[str, Any] = {
#                 "model": self.model,
#                 "messages": chat_messages,
#             }
#
#             # Tools
#             if tools:
#                 payload["tools"] = [tool_to_openai_definition(t) for t in tools]
#                 payload["tool_choice"] = (
#                     "required" if force_tool_call and round_counter == 1 else "auto"
#                 )
#
#             # Structured response
#             if response_model is not None:
#                 payload["response_format"] = json_response_format(
#                     response_model.__name__,
#                     response_model.model_json_schema(),
#                 )
#
#             logger.debug("LLM payload (round %s): %s", round_counter, json.dumps(payload, default=str)[:2000])
#
#             response = self.client.chat.completions.create(**payload)
#             choice = response.choices[0]
#             msg = choice.message
#
#             logger.debug("LLM raw response (round %s): %s", round_counter, msg)
#
#             # If the assistant requested tools:
#             if msg.tool_calls:
#                 # append the assistant message with tool_calls
#                 chat_messages.append(
#                     ChatCompletionAssistantMessageParam(
#                         role="assistant",
#                         content=msg.content or "",
#                         tool_calls=msg.tool_calls,  # type: ignore
#                     )
#                 )
#
#                 for call in cast(List[ChatCompletionMessageFunctionToolCall], msg.tool_calls):
#                     tool_name = call.function.name
#                     tool = self.registry.get(tool_name)
#                     try:
#                         raw_args = json.loads(call.function.arguments or "{}")
#                     except json.JSONDecodeError as e:
#                         logger.error("Failed to decode tool args for %s: %s", tool_name, e)
#                         tool_result = {"error": f"Invalid JSON arguments: {str(e)}"}
#                     else:
#                         # Validate args with Pydantic
#                         try:
#                             args_obj = tool.args_model.model_validate(raw_args)
#                         except ValidationError as ve:
#                             logger.error("Tool args validation error for %s: %s", tool_name, ve)
#                             tool_result = {"error": f"Argument validation error: {ve.errors()}"}
#                         else:
#                             # Call the actual tool
#                             if tool.is_async:
#                                 raise RuntimeError(
#                                     f"Tool '{tool.name}' is async. "
#                                     "Use 'achat' instead of 'chat' for this tool."
#                                 )
#                             try:
#                                 result = tool.func(**args_obj.model_dump())
#                                 if isinstance(result, BaseModel):
#                                     result_dict = result.model_dump()
#                                 elif tool.result_model is not None:
#                                     # Coerce into result_model if provided
#                                     result_dict = tool.result_model.model_validate(result).model_dump()
#                                 else:
#                                     result_dict = result
#                                 tool_result = result_dict
#                             except Exception as e:
#                                 logger.error("Error while executing tool %s: %s", tool_name, e, exc_info=True)
#                                 tool_result = {"error": str(e)}
#
#                     chat_messages.append(
#                         ChatCompletionToolMessageParam(
#                             role="tool",
#                             tool_call_id=call.id,
#                             content=json.dumps(tool_result),
#                         )
#                     )
#
#                 # Go next round after all tools processed
#                 continue
#
#             # No tool calls: final content
#             if msg.content:
#                 content_str = msg.content
#                 if response_model is None:
#                     results.append(content_str)
#                 else:
#                     # Try to parse content as JSON matching response_model
#                     try:
#                         parsed = response_model.model_validate_json(content_str)
#                         results.append(parsed)
#                     except ValidationError as ve:
#                         # Give model a chance to self-correct by sending error back
#                         logger.warning("Response validation failed: %s", ve)
#                         chat_messages.append(
#                             make_message(
#                                 "user",
#                                 content=(
#                                     f"Your last response did not match the required JSON schema for "
#                                     f"{response_model.__name__}. Validation error: {ve}"
#                                 ),
#                             )
#                         )
#                         # Let the next round try again
#                         continue
#
#                 # If we got content successfully, break the loop
#                 break
#
#             # No content, no tool calls → weird, bail out
#             logger.warning("Assistant returned neither content nor tool_calls; stopping.")
#             break
#
#         if round_counter >= self.max_rounds and not results:
#             raise RuntimeError("Exceeded maximum number of rounds without final content")
#
#         return results  # type:ignore
#
#     # ---------------- async ----------------
#
#     async def achat(
#         self,
#         messages: Sequence[Message],
#         *,
#         response_model: Optional[Type[BaseModel]] = None,
#         tool_names: Optional[Iterable[str]] = None,
#         force_tool_call: bool = False,
#     ) -> Union[List[str], List[BaseModel]]:
#         """
#         Async version of chat(). Supports async tools and better concurrency.
#         """
#         tools = self.registry.select(tool_names) if self.registry else []
#         chat_messages: List[ChatCompletionMessageParam] = [
#             make_message(m["role"], m["content"]) for m in messages
#         ]
#
#         round_counter = 0
#         results: List[Union[str, BaseModel]] = []
#
#         while round_counter < self.max_rounds:
#             round_counter += 1
#
#             payload: Dict[str, Any] = {
#                 "model": self.model,
#                 "messages": chat_messages,
#             }
#
#             if tools:
#                 payload["tools"] = [tool_to_openai_definition(t) for t in tools]
#                 payload["tool_choice"] = (
#                     "required" if force_tool_call and round_counter == 1 else "auto"
#                 )
#
#             if response_model is not None:
#                 payload["response_format"] = json_response_format(
#                     response_model.__name__,
#                     response_model.model_json_schema(),
#                 )
#
#             logger.debug("LLM async payload (round %s): %s", round_counter, json.dumps(payload, default=str)[:2000])
#
#             response = await self.client.chat.completions.create_async(**payload)  # type: ignore[attr-defined]
#             choice = response.choices[0]
#             msg = choice.message
#
#             logger.debug("LLM async raw response (round %s): %s", round_counter, msg)
#
#             if msg.tool_calls:
#                 chat_messages.append(
#                     ChatCompletionAssistantMessageParam(
#                         role="assistant",
#                         content=msg.content or "",
#                         tool_calls=msg.tool_calls,
#                     )
#                 )
#
#                 for call in cast(List[ChatCompletionMessageFunctionToolCall], msg.tool_calls):
#                     tool_name = call.function.name
#                     tool = self.registry.get(tool_name)
#
#                     try:
#                         raw_args = json.loads(call.function.arguments or "{}")
#                     except json.JSONDecodeError as e:
#                         logger.error("Failed to decode tool args for %s: %s", tool_name, e)
#                         tool_result = {"error": f"Invalid JSON arguments: {str(e)}"}
#                     else:
#                         try:
#                             args_obj = tool.args_model.model_validate(raw_args)
#                         except ValidationError as ve:
#                             logger.error("Tool args validation error for %s: %s", tool_name, ve)
#                             tool_result = {"error": f"Argument validation error: {ve.errors()}"}
#                         else:
#                             try:
#                                 if tool.is_async:
#                                     result = await tool.func(**args_obj.model_dump())
#                                 else:
#                                     loop = asyncio.get_running_loop()
#                                     bound = partial(tool.func, **args_obj.model_dump())
#                                     result = await loop.run_in_executor(None, bound)  # type: ignore
#
#                                 if isinstance(result, BaseModel):
#                                     result_dict = result.model_dump()
#                                 elif tool.result_model is not None:
#                                     result_dict = tool.result_model.model_validate(result).model_dump()
#                                 else:
#                                     result_dict = result
#                                 tool_result = result_dict
#                             except Exception as e:
#                                 logger.error("Error while executing tool %s: %s", tool_name, e, exc_info=True)
#                                 tool_result = {"error": str(e)}
#
#                     chat_messages.append(
#                         ChatCompletionToolMessageParam(
#                             role="tool",
#                             tool_call_id=call.id,
#                             content=json.dumps(tool_result),
#                         )
#                     )
#
#                 continue
#
#             if msg.content:
#                 content_str = msg.content
#                 if response_model is None:
#                     results.append(content_str)
#                 else:
#                     try:
#                         parsed = response_model.model_validate_json(content_str)
#                         results.append(parsed)
#                     except ValidationError as ve:
#                         logger.warning("Async response validation failed: %s", ve)
#                         chat_messages.append(
#                             make_message(
#                                 "user",
#                                 content=(
#                                     f"Your last response did not match the required JSON schema for "
#                                     f"{response_model.__name__}. Validation error: {ve}"
#                                 ),
#                             )
#                         )
#                         continue
#
#                 break
#
#             logger.warning("Async assistant returned neither content nor tool_calls; stopping.")
#             break
#
#         if round_counter >= self.max_rounds and not results:
#             raise RuntimeError("Exceeded maximum number of rounds without final content (async)")
#
#         return results  # type: ignore
#


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
