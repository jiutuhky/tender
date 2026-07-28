from hagent.server.sse import SSEFormatter, TASK_TOOL_NAMES, parse_lg_chunk


def test_sse_format_simple_event():
    fmt = SSEFormatter()
    out = fmt.format(event="message.delta", data={"content_chunk": "hello"})
    assert b"event: message.delta\n" in out
    assert b'"content_chunk": "hello"' in out
    assert out.endswith(b"\n\n")


def test_sse_format_includes_id():
    fmt = SSEFormatter()
    first = fmt.format(event="x", data={})
    out = fmt.format(event="y", data={})
    assert b"id: 0\n" in first
    assert b"id: 1\n" in out


def test_parse_messages_chunk_to_message_delta():
    # LangGraph stream_mode='messages' 返回 (token, metadata) 元组
    class FakeAIChunk:
        type = "AIMessageChunk"
        content = "hi"
        tool_call_chunks = []

    out = list(parse_lg_chunk(("messages", (FakeAIChunk(), {}))))
    assert len(out) == 1
    event, data = out[0]
    assert event == "message.delta"
    assert data["content_chunk"] == "hi"


def test_parse_tool_call_chunk_to_tool_call_started():
    class FakeToolCallStart:
        type = "AIMessageChunk"
        content = ""
        tool_call_chunks = [{"name": "read_file", "args": '{"path":', "id": "abc", "index": 0}]

    out = list(parse_lg_chunk(("messages", (FakeToolCallStart(), {}))))
    assert any(e == "tool_call.started" for e, _ in out)


def test_parse_tool_call_args_chunks_without_repeated_name():
    class FakeToolCallStart:
        type = "AIMessageChunk"
        content = ""
        tool_call_chunks = [{"name": "execute", "args": "", "id": "abc", "index": 0}]

    class FakeToolCallArgs:
        type = "AIMessageChunk"
        content = ""
        tool_call_chunks = [{"name": None, "args": '{"command":"pytest"}', "id": None, "index": 0}]

    tool_call_state = {}
    list(parse_lg_chunk(("messages", (FakeToolCallStart(), {})), tool_call_state=tool_call_state))

    out = list(parse_lg_chunk(("messages", (FakeToolCallArgs(), {})), tool_call_state=tool_call_state))

    assert out == [
        (
            "tool_call.started",
            {
                "call_id": "abc",
                "tool_name": "execute",
                "args_chunk": '{"command":"pytest"}',
                "parent_tool_use_id": None,
            },
        )
    ]


def test_parse_bash_tool_call_args_chunks_preserve_bash_name():
    class FakeToolCallStart:
        type = "AIMessageChunk"
        content = ""
        tool_call_chunks = [{"name": "Bash", "args": "", "id": "abc", "index": 0}]

    class FakeToolCallArgs:
        type = "AIMessageChunk"
        content = ""
        tool_call_chunks = [{"name": None, "args": '{"command":"pytest"}', "id": None, "index": 0}]

    tool_call_state = {}
    list(parse_lg_chunk(("messages", (FakeToolCallStart(), {})), tool_call_state=tool_call_state))

    out = list(parse_lg_chunk(("messages", (FakeToolCallArgs(), {})), tool_call_state=tool_call_state))

    assert out == [
        (
            "tool_call.started",
            {
                "call_id": "abc",
                "tool_name": "Bash",
                "args_chunk": '{"command":"pytest"}',
                "parent_tool_use_id": None,
            },
        )
    ]


def test_parse_tool_message_to_tool_call_completed():
    class FakeToolMessage:
        type = "tool"
        content = "result"
        tool_call_id = "abc"
        name = "read_file"

    out = list(parse_lg_chunk(("messages", (FakeToolMessage(), {}))))
    assert any(e == "tool_call.completed" for e, _ in out)


def test_parse_tool_message_preserves_full_result():
    class FakeToolMessage:
        type = "tool"
        content = "x" * 1200
        tool_call_id = "abc"
        name = "Skill"

    out = list(parse_lg_chunk(("messages", (FakeToolMessage(), {}))))

    completed = [data for event, data in out if event == "tool_call.completed"]
    assert completed[0]["result_summary"] == "x" * 1200


def test_parse_interrupt_preserves_full_payload():
    payload = {"message": "x" * 1200}

    out = list(parse_lg_chunk(("updates", {"__interrupt__": payload})))

    interrupts = [data for event, data in out if event == "interrupt.requested"]
    assert interrupts[0]["payload"] == str(payload)


def test_parse_content_list_passes_blocks_through_raw():
    # 真实模型（如 Anthropic extended thinking）返回 content=list[content-block]；
    # adapter 不做过滤、不拼接 —— 前端按 block.type 自己渲染 thinking / text 等。
    blocks = [
        {"type": "thinking", "thinking": "let me think"},
        {"type": "text", "text": "hello world"},
    ]

    class FakeAIChunk:
        type = "AIMessageChunk"
        content = blocks
        tool_call_chunks = []

    out = list(parse_lg_chunk(("messages", (FakeAIChunk(), {}))))
    deltas = [d for e, d in out if e == "message.delta"]
    assert len(deltas) == 1
    assert deltas[0]["content_chunk"] == blocks  # 原样透传


def test_parse_content_list_thinking_only_still_emits_delta():
    # 即使只有 thinking 块，也照发 message.delta —— 前端会显示推理过程。
    class FakeAIChunk:
        type = "AIMessageChunk"
        content = [{"type": "thinking", "thinking": "reasoning..."}]
        tool_call_chunks = []

    out = list(parse_lg_chunk(("messages", (FakeAIChunk(), {}))))
    deltas = [d for e, d in out if e == "message.delta"]
    assert len(deltas) == 1
    assert deltas[0]["content_chunk"] == [{"type": "thinking", "thinking": "reasoning..."}]


def test_parse_task_tool_completion_requests_todo_refresh():
    class FakeToolMessage:
        type = "tool"
        content = "Updated task 1"
        tool_call_id = "abc"
        name = "TaskUpdate"

    out = list(parse_lg_chunk(("messages", (FakeToolMessage(), {}))))

    assert TASK_TOOL_NAMES == {"TaskCreate", "TaskGet", "TaskUpdate", "TaskList"}
    assert ("tool_call.completed", {
        "call_id": "abc",
        "tool_name": "TaskUpdate",
        "result_summary": "Updated task 1",
        "parent_tool_use_id": None,
    }) in out
    assert ("todo.refresh_requested", {"tool_name": "TaskUpdate"}) in out


def test_parse_non_task_tool_completion_does_not_request_todo_refresh():
    class FakeToolMessage:
        type = "tool"
        content = "result"
        tool_call_id = "abc"
        name = "read_file"

    out = list(parse_lg_chunk(("messages", (FakeToolMessage(), {}))))

    assert any(e == "tool_call.completed" for e, _ in out)
    assert not any(e == "todo.refresh_requested" for e, _ in out)


def test_parse_write_todos_completion_does_not_emit_todo_events():
    class FakeToolMessage:
        type = "tool"
        content = '[{"content": "do x", "status": "pending"}]'
        tool_call_id = "abc"
        name = "write_todos"

    out = list(parse_lg_chunk(("messages", (FakeToolMessage(), {}))))
    assert any(e == "tool_call.completed" for e, _ in out)
    assert not any(e == "todo.updated" for e, _ in out)
    assert not any(e == "todo.refresh_requested" for e, _ in out)


# --- 子代理归属：parent_tool_use_id (CC 的 parentToolUseID 对齐) ---
#
# hagent 自管 Agent 工具走工具内 runnable.invoke，subgraph namespace 的 task-id
# 不等于 Agent 的 tool_call_id（同一轮并行子代理还会共享 namespace 前缀），故归属
# 不能从 namespace 抽。改由 Agent 工具把自己的 tool_call_id 注入子代理 config
# metadata，stream_mode="messages" 的 token metadata 即带上 parent_tool_use_id。
# adapter 负责把它挂到每个事件 data 上；主 agent（无 meta）为 None。


def test_message_delta_carries_parent_tool_use_id_from_meta():
    class FakeAIChunk:
        type = "AIMessageChunk"
        content = "hi from subagent"
        tool_call_chunks = []

    out = list(parse_lg_chunk(("messages", (FakeAIChunk(), {"parent_tool_use_id": "agent-1"}))))
    assert out == [
        ("message.delta", {
            "role": "assistant",
            "content_chunk": "hi from subagent",
            "parent_tool_use_id": "agent-1",
        })
    ]


def test_message_delta_parent_tool_use_id_is_none_for_main_agent():
    class FakeAIChunk:
        type = "AIMessageChunk"
        content = "hi from main"
        tool_call_chunks = []

    out = list(parse_lg_chunk(("messages", (FakeAIChunk(), {}))))
    event, data = out[0]
    assert event == "message.delta"
    assert data["parent_tool_use_id"] is None


def test_tool_call_started_carries_parent_tool_use_id():
    class FakeToolCallStart:
        type = "AIMessageChunk"
        content = ""
        tool_call_chunks = [{"name": "Read", "args": "", "id": "read-9", "index": 0}]

    out = list(parse_lg_chunk(("messages", (FakeToolCallStart(), {"parent_tool_use_id": "agent-1"}))))
    started = [d for e, d in out if e == "tool_call.started"]
    assert started and started[0]["parent_tool_use_id"] == "agent-1"


def test_tool_call_completed_carries_parent_tool_use_id():
    class FakeToolMessage:
        type = "tool"
        content = "result"
        tool_call_id = "read-9"
        name = "Read"

    out = list(parse_lg_chunk(("messages", (FakeToolMessage(), {"parent_tool_use_id": "agent-1"}))))
    completed = [d for e, d in out if e == "tool_call.completed"]
    assert completed and completed[0]["parent_tool_use_id"] == "agent-1"
