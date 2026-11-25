from pathlib import Path

from daneel.core import Message
from daneel.storage import SessionStore


def test_create_list_and_load(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3")

    first = store.create_session("First chat", model="qwen2.5:1.5b", reply_mode="auto")
    store.append_messages(
        first,
        [Message("user", "hi"), Message("assistant", "hello")],
        title="Привет",
    )
    second = store.create_session("Second chat")
    store.append_messages(second, [Message("user", "question")])

    sessions = store.list_sessions()
    assert [session.id for session in sessions] == [second, first]
    assert sessions[1].title == "Привет"
    assert sessions[1].message_count == 2

    assert [
        (message.role, message.content)
        for message in store.load_messages(first)
    ] == [("user", "hi"), ("assistant", "hello")]
    store.close()


def test_tool_calls_are_preserved(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session_id = store.create_session("Tools")
    message = Message(
        "assistant",
        "",
        tool_calls=[{"name": "echo", "arguments": {"value": "hi"}}],
    )

    store.append_messages(session_id, [message])

    loaded = store.load_messages(session_id)
    assert loaded[0].tool_calls == message.tool_calls
    store.close()


def test_delete_session_cascades(tmp_path: Path) -> None:
    store = SessionStore(tmp_path / "sessions.sqlite3")
    session_id = store.create_session("To delete")
    store.append_messages(session_id, [Message("user", "hi")])

    assert store.delete_session(session_id) is True
    assert store.get_session(session_id) is None
    assert store.load_messages(session_id) == []
    assert store.delete_session(session_id) is False
    store.close()
