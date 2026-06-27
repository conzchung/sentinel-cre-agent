import os
import uuid
import importlib
from copy import deepcopy

from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union, Annotated
from azure.storage.blob.aio import BlobServiceClient
from azure.storage.blob import generate_blob_sas, BlobSasPermissions, ContentSettings
from datetime import datetime, timedelta, timezone

from langchain_core.prompts import PromptTemplate
from langchain_core.messages import ToolMessage, HumanMessage, AIMessage, SystemMessage
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda
from langgraph.prebuilt import ToolNode, tools_condition, InjectedState
from langchain_core.output_parsers import JsonOutputParser, StrOutputParser
from langchain_core.messages.utils import count_tokens_approximately, convert_to_messages
from langchain_core.messages import (
    AnyMessage,
    MessageLikeRepresentation,
    RemoveMessage
)

from collections.abc import Iterable, Sequence
from azure.cosmos.aio import CosmosClient
from azure.cosmos.exceptions import CosmosResourceNotFoundError

from models import init_llm, GPT54m_args

from db import hong_kong_tz


def parse_account_from_connection_string(conn_str: str) -> Tuple[str, str]:
    """
    Extracts account_name and account_key from an Azure Storage connection string.

    Raises KeyError if either is missing.
    Expected connection string format contains:
        AccountName=...;AccountKey=...;...
    """
    parts: dict[str, str] = {}
    for kv in conn_str.split(";"):
        if not kv:
            continue
        key, value = kv.split("=", 1)
        parts[key] = value

    account_name = parts["AccountName"]
    account_key = parts["AccountKey"]
    return account_name, account_key


AccessMode = Literal["public", "sas"]

async def upload_blob_and_get_url(
    container_name: str,
    blob_name: str,
    data: Union[bytes, str],
    blob_service_client: BlobServiceClient,
    conn_str: str = os.getenv('BLOB_CONNECTION_STRING'),
    access_mode: AccessMode = "sas",
    expiry_days: int = 365,
    content_type: Optional[str] = None,
) -> str:
    """
    Async: Uploads a blob to Azure Blob Storage and returns a URL.

    Supports two modes:
      - access_mode="public":
            returns a plain URL (no SAS).
            REQUIRES: the container is configured to allow
                      anonymous read for blobs in Azure Portal.

      - access_mode="sas":
            returns a SAS URL with read permission.
            Container can be private, but the connection string MUST
            contain AccountKey (shared key auth).

    Args:
        container_name: Name of the container.
        blob_name: Blob name (path inside container).
        data: Blob content (bytes or str).
        blob_service_client: Async BlobServiceClient built from the same account as conn_str.
        conn_str: The connection string used to create blob_service_client.
        access_mode: "public" or "sas".
        expiry_days: SAS validity in days (only used in "sas" mode).
        content_type: Optional MIME type for the blob.

    Returns:
        str: URL (plain or SAS) to access the blob.
    """
    # Ensure container exists
    container_client = blob_service_client.get_container_client(container_name)
    if not await container_client.exists():
        await container_client.create_container()

    # Upload blob
    blob_client = container_client.get_blob_client(blob_name)

    upload_kwargs = {"overwrite": True}
    if content_type:
        upload_kwargs["content_settings"] = ContentSettings(content_type=content_type)

    await blob_client.upload_blob(data, **upload_kwargs)

    # Public mode: just return direct URL (no SAS)
    if access_mode == "public":
        return blob_client.url

    # SAS mode: generate a signed URL
    if access_mode == "sas":
        account_name, account_key = parse_account_from_connection_string(conn_str)

        expiry_time = datetime.now(timezone.utc) + timedelta(days=expiry_days)

        sas_token = generate_blob_sas(
            account_name=account_name,
            container_name=container_name,
            blob_name=blob_name,
            account_key=account_key,
            permission=BlobSasPermissions(read=True),
            expiry=expiry_time,
        )

        return f"{blob_client.url}?{sas_token}"

    # Safety: unsupported mode
    raise ValueError(f"Unsupported access_mode: {access_mode}")


def import_function(module_name, function_name):
    module = importlib.import_module(module_name)
    return getattr(module, function_name)


def convert_tools(tools_config):
    imported_functions = []

    # Import functions dynamically from their respective modules and store them in a list
    for tool_config in tools_config:
        module_name = tool_config["module"]
        for function_name in tool_config["function"]:
            func = import_function(module_name, function_name)
            imported_functions.append(func)

    return imported_functions


def safe_slice_messages(messages, messages_to_keep):
    """
    Slice messages into (messages_for_summary, recent_messages)
    without breaking AIMessage+ToolMessages groups.
    Enforces: len(AIMessage.tool_calls) == number of ToolMessages after it.
    """
    messages_to_keep = max(messages_to_keep, 1)
    split_index = len(messages) - messages_to_keep

    # Scan backwards to ensure we don't split a tool group
    while split_index > 0:
        current_msg = messages[split_index]

        # Case 1: We landed on a ToolMessage → move split_index back to its AIMessage
        if isinstance(current_msg, ToolMessage):
            split_index -= 1
            continue

        # Case 2: We landed on an AIMessage with tool_calls
        if isinstance(current_msg, AIMessage) and getattr(current_msg, "tool_calls", None):
            num_tool_calls = len(current_msg.tool_calls)

            # Count consecutive ToolMessages after this AIMessage
            tool_msgs_after = 0
            for i in range(split_index + 1, len(messages)):
                if isinstance(messages[i], ToolMessage):
                    tool_msgs_after += 1
                else:
                    break

            # If counts don't match, or we are splitting the group → move split_index back
            if tool_msgs_after != num_tool_calls:
                # Move split_index back so the entire group is in recent_messages
                split_index -= 1
                continue
            else:
                # Keep AIMessage + all ToolMessages together in recent_messages
                split_index = split_index
                break

        break  # No special case → we can stop adjusting

    messages_for_summary = messages[:split_index]
    recent_messages = messages[split_index:]

    return messages_for_summary, recent_messages


async def summarize_conversation(messages: Iterable[MessageLikeRepresentation], messages_to_keep=10):

    DEFAULT_SUMMARY_PROMPT = """<role>
Context Extraction Assistant
</role>

<primary_objective>
Your sole objective in this task is to extract the highest quality/most relevant context from the conversation history below.
</primary_objective>

<objective_information>
You're nearing the total number of input tokens you can accept, so you must extract the highest quality/most relevant pieces of information from your conversation history.
This context will then overwrite the conversation history presented below. Because of this, ensure the context you extract is only the most important information to your overall goal.
</objective_information>

<instructions>
The conversation history below will be replaced with the context you extract in this step. Because of this, you must do your very best to extract and record all of the most important context from the conversation history.
You want to ensure that you don't repeat any actions you've already completed, so the context you extract from the conversation history should be focused on the most important information to your overall goal.
</instructions>

The user will message you with the full message history you'll be extracting context from, to then replace. Carefully read over it all, and think deeply about what information is most important to your overall goal that should be saved:

With all of this in mind, please carefully read over the entire conversation history, and extract the most important and relevant context to replace it so that you can free up space in the conversation history.
Respond ONLY with the extracted context. Do not include any additional information, or text before or after the extracted context.

<messages>
Messages to summarize:
{messages}
</messages>"""

    template = DEFAULT_SUMMARY_PROMPT

    llm = init_llm(GPT54m_args)
    prompt = PromptTemplate(template=template, input_variables=['messages'])
    chain = prompt | llm | StrOutputParser()

    messages_to_keep = max(messages_to_keep, 1)

    # Determine the split point
    if messages_to_keep >= len(messages):
        # Nothing to summarize, just return messages
        return messages

    messages_for_summary, recent_messages = safe_slice_messages(messages, messages_to_keep)

    converted_messages = convert_to_messages(messages_for_summary)

    extracted_messages = []
    for msg in converted_messages:
        if isinstance(msg, HumanMessage):
            content = f"user message:\n{msg.content}"
        elif isinstance(msg, ToolMessage):
            content = f"tool output:\n{msg.content}"
        elif isinstance(msg, AIMessage):
            if len(msg.tool_calls) > 0:
                tool_call_str = ""
                for tool_call in msg.tool_calls:
                    tool_call_str += str(tool_call)
                content = f"tool calls by assistant:\n{tool_call_str}"
            else:
                content = f"assistant:\n{msg.content}"
        else:
            content = ""
        extracted_messages.append(content)
    # print(len(extracted_messages))

    summarized_conversation = await chain.ainvoke({'messages': extracted_messages})
    summary = f"Here is a summary of the conversation to date:\n\n{summarized_conversation}"

    condensed_messages = [HumanMessage(content=summary, id=str(uuid.uuid4()))] + recent_messages

    return condensed_messages


def repair_missing_tool_messages(messages: List[MessageLikeRepresentation]) -> List[MessageLikeRepresentation]:
    """
    Ensures that any AIMessage with tool_calls is immediately followed by ToolMessages
    (one for each tool call). If any are missing, inserts a 'Failed in tool call' ToolMessage
    right after the AIMessage.
    """
    repaired_messages = []
    i = 0

    while i < len(messages):
        msg = messages[i]
        repaired_messages.append(msg)

        # If this is an AIMessage with tool_calls
        if isinstance(msg, AIMessage) and getattr(msg, "tool_calls", None):
            # Collect existing tool messages immediately following
            existing_tools = []
            j = i + 1
            while j < len(messages) and isinstance(messages[j], ToolMessage):
                existing_tools.append(messages[j])
                repaired_messages.append(messages[j])
                j += 1

            # Build a set of existing tool_call_ids
            existing_ids = {tm.tool_call_id for tm in existing_tools}

            # Insert missing ToolMessages
            for tc in msg.tool_calls:
                tc_id = tc.get("id")
                if tc_id not in existing_ids:
                    repaired_messages.append(
                        ToolMessage(
                            content="Tool call failed. Retry on next user request.",
                            tool_call_id=tc_id,
                            id=str(uuid.uuid4())
                        )
                    )

            # Continue from the next non-tool message
            i = j
        else:
            i += 1

    return repaired_messages


### langgraph helper functions ###
def handle_tool_error(state) -> dict:
    error = state.get("error")
    tool_calls = state["messages"][-1].tool_calls
    return {
        "messages": [
            ToolMessage(
                content=f"Error: {repr(error)}\n please fix your mistakes.",
                tool_call_id=tc["id"],
            )
            for tc in tool_calls
        ]
    }


def create_tool_node_with_fallback(tools: list) -> dict:
    return ToolNode(tools).with_fallbacks(
        [RunnableLambda(handle_tool_error)], exception_key="error"
    )


def _print_event(event: dict, _printed: set, max_length=6000):
    current_state = event.get("dialog_state")
    if current_state:
        print("Currently in:", current_state[-1])
    message = event.get("messages")
    if message:
        if isinstance(message, list):
            message = message[-1]
        if isinstance(message, HumanMessage):
            new_max_length = 1000
        elif isinstance(message, ToolMessage):
            new_max_length = 500
        else:
            new_max_length = max_length
        if message.id not in _printed:
            msg_repr = message.pretty_repr(html=True)
            if len(msg_repr) > max_length:
                msg_repr = msg_repr[:new_max_length] + " ... (truncated)"
            print(msg_repr)
            _printed.add(message.id)
            return message
        
        
def combine_human_message_with_images(message: str, image_urls: List[str] = None) -> HumanMessage:
    
    combined_prompt = message.strip()

    if image_urls:
        for i, img_url in enumerate(image_urls, start=1):
            image_prompt = f"\n{i}. {img_url}"
            combined_prompt += image_prompt

    return HumanMessage(content=combined_prompt)


def print_todos(todos):
    output_lines = []
    
    if not todos:
        output_lines.append("No todos available.")
    else:
        output_lines.append("***** Execution plan *****")
        for index, todo in enumerate(todos, 1):  # Start numbering from 1
            output_lines.append(f"{index}. Content: {todo['content']}")
            output_lines.append(f"   Status: {todo['status']}")
            if 'remarks' in todo and todo['remarks'] is not None:
                output_lines.append(f"   Remarks: {todo['remarks']}")
    
    # Join all lines into a single string
    output_str = "\n".join(output_lines)
    
    # print(output_str)  # Still prints to console
    return output_str   # Also returns the string


def prepare_last_todos(todos):

    copied_todos = deepcopy(todos)

    new_todos = []
    for todo in copied_todos:
        if todo['status'] in ['in_progress']:
            todo['status'] = 'completed'
        new_todos.append(todo)

    return new_todos


async def _upsert_chat_document(
    container,
    thread_id: str,
    message: Dict[str, Any],
    user_id: Optional[str] = None,
    token_usage: Optional[Dict[str, int]] = None,
) -> None:
    """
    Common upsert logic for both dialog and log containers.
    Assumes partition key is 'thread_id'.
    """
    try:
        # Read existing doc (id == thread_id, partition_key == thread_id)
        doc = await container.read_item(item=thread_id, partition_key=thread_id)

        # Append message
        dialog = doc.get("dialog") or []
        dialog.append(message)
        doc["dialog"] = dialog

        # Meta fields
        if user_id is not None:
            # optional: only overwrite if a new user_id is provided
            doc["user_id"] = user_id
        doc["updated_at"] = datetime.now(hong_kong_tz).strftime("%Y/%m/%d %H:%M:%S")

        # Token usage
        updated_token_usage = token_usage
        if token_usage:
            existing_usage = doc.get(
                "total_token_usage",
                {
                    "total_tokens": 0,
                    "prompt_tokens": 0,
                    "completion_tokens": 0,
                },
            )
            updated_token_usage = {
                "total_tokens": existing_usage.get("total_tokens", 0)
                + token_usage.get("total_tokens", 0),
                "prompt_tokens": existing_usage.get("prompt_tokens", 0)
                + token_usage.get("prompt_tokens", 0),
                "completion_tokens": existing_usage.get("completion_tokens", 0)
                + token_usage.get("completion_tokens", 0),
            }

        doc["total_token_usage"] = updated_token_usage

        # Set convo_title from first *user* message if not already set
        if not doc.get("convo_title") and message.get("role") == "user":
            doc["convo_title"] = message.get("content")

    except CosmosResourceNotFoundError:
        now_str = datetime.now(hong_kong_tz).strftime("%Y/%m/%d %H:%M:%S")

        # For a new document, set convo_title only if this first message is from a user
        convo_title = message.get("content") if message.get("role") == "user" else None

        # New document
        doc = {
            "id": thread_id,           
            "thread_id": thread_id,    
            "user_id": user_id,
            "dialog": [message],
            "created_at": now_str,
            "updated_at": now_str,
            "total_token_usage": token_usage,
            "convo_title": convo_title,
        }

    # Upsert: create or replace
    await container.upsert_item(doc)


def get_state(tool_name: str) -> str:
    research = {
        "perform_online_search",
    }
    visualization = {
        "generate_image",
        "comprehend_image"
    }

    if tool_name in research:
        return "Research Assistant"
    if tool_name in visualization:
        return "Visualization Assistant"
    return "Primary Assistant"


def get_action(tool_name: str) -> str:
    action_dict = {
        "generate_image": "Generate Image",
        "perform_online_search": "Conduct Online Search",
        "comprehend_image": "Comprehend Images",
    }
    return action_dict.get(tool_name, "Respond to User Query")