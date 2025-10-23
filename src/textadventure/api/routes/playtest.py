"""Playtest routes for WebSocket-based adventure testing and transcripts."""

from __future__ import annotations

import uuid
from typing import Any, Callable, Mapping

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect  # type: ignore[attr-defined]

from ..models import PlaytestTranscriptResponse


def create_playtest_router(
    playtest_manager: Any,
    active_sessions: dict[str, Any],
    *,
    build_transcript_entries_fn: Callable[..., Any],
    build_transcript_message_fn: Callable[..., Any],
    build_error_message_fn: Callable[..., Any],
    build_event_message_fn: Callable[..., Any],
) -> APIRouter:
    """Create the playtest router with injected dependencies.

    Args:
        playtest_manager: Manager for creating playtest sessions
        active_sessions: Dictionary tracking active WebSocket sessions
        build_transcript_entries_fn: Helper to build transcript entries
        build_error_message_fn: Helper to build error messages
        build_event_message_fn: Helper to build event messages

    Returns:
        Configured APIRouter instance with playtest routes
    """
    router = APIRouter()

    # Playtest Routes

    @router.get(
        "/api/playtest/sessions/{session_id}/transcript",
        response_model=PlaytestTranscriptResponse,
        tags=["Playtest"],
    )
    def get_playtest_transcript(session_id: str) -> PlaytestTranscriptResponse:
        session = active_sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Playtest session not found.")

        return PlaytestTranscriptResponse(
            session_id=session_id,
            entries=build_transcript_entries_fn(session),
        )

    @router.delete(
        "/api/playtest/sessions/{session_id}/transcript",
        status_code=204,
        tags=["Playtest"],
    )
    def clear_playtest_transcript(session_id: str) -> None:
        session = active_sessions.get(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Playtest session not found.")

        session.clear_transcript()

    @router.websocket("/api/playtest")
    def playtest_endpoint(websocket: WebSocket) -> None:
        websocket.accept()

        initial_project_id = websocket.query_params.get("project_id")
        session_id = uuid.uuid4().hex

        try:
            try:
                session = playtest_manager.create_session(project_id=initial_project_id)
                initial_event = session.reset()
            except FileNotFoundError as exc:
                websocket.send_json(
                    build_error_message_fn("project-not-found", str(exc)).model_dump(
                        mode="json"
                    )
                )
                websocket.close(code=4404)
                return
            except ValueError as exc:
                websocket.send_json(
                    build_error_message_fn("invalid-project", str(exc)).model_dump(
                        mode="json"
                    )
                )
                websocket.close(code=4400)
                return
            except RuntimeError as exc:
                websocket.send_json(
                    build_error_message_fn("session-error", str(exc)).model_dump(
                        mode="json"
                    )
                )
                websocket.close(code=1011)
                return

            active_sessions[session_id] = session

            websocket.send_json(
                build_event_message_fn(
                    initial_event,
                    session,
                    session_id=session_id,
                ).model_dump(mode="json")
            )

            while True:
                try:
                    payload = websocket.receive_json()
                except WebSocketDisconnect:
                    break

                if not isinstance(payload, Mapping):
                    websocket.send_json(
                        build_error_message_fn(
                            "invalid-message", "Payload must be a JSON object."
                        ).model_dump(mode="json")
                    )
                    continue

                raw_type = payload.get("type")
                if not isinstance(raw_type, str):
                    websocket.send_json(
                        build_error_message_fn(
                            "invalid-message", "Message type must be a string."
                        ).model_dump(mode="json")
                    )
                    continue

                message_type = raw_type.strip().lower()

                if message_type == "player_input":
                    command_value = payload.get("input", "")
                    if not isinstance(command_value, str):
                        websocket.send_json(
                            build_error_message_fn(
                                "invalid-message", "Player input must be a string."
                            ).model_dump(mode="json")
                        )
                        continue
                    try:
                        event = session.apply_player_input(command_value)
                    except Exception as exc:  # pragma: no cover - surfaced to client
                        websocket.send_json(
                            build_error_message_fn(
                                "session-error", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue
                    websocket.send_json(
                        build_event_message_fn(
                            event,
                            session,
                            session_id=session_id,
                        ).model_dump(mode="json")
                    )
                    continue

                if message_type == "reset":
                    try:
                        event = session.reset()
                    except Exception as exc:  # pragma: no cover - surfaced to client
                        websocket.send_json(
                            build_error_message_fn(
                                "session-error", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue
                    websocket.send_json(
                        build_event_message_fn(
                            event,
                            session,
                            session_id=session_id,
                        ).model_dump(mode="json")
                    )
                    continue

                if message_type == "configure":
                    project_value = payload.get("project_id")
                    if not isinstance(project_value, str) or not project_value.strip():
                        websocket.send_json(
                            build_error_message_fn(
                                "invalid-project",
                                "Project identifier must be a non-empty string.",
                            ).model_dump(mode="json")
                        )
                        continue
                    try:
                        new_session = playtest_manager.create_session(
                            project_id=project_value
                        )
                        event = new_session.reset()
                    except FileNotFoundError as exc:
                        websocket.send_json(
                            build_error_message_fn(
                                "project-not-found", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue
                    except ValueError as exc:
                        websocket.send_json(
                            build_error_message_fn(
                                "invalid-project", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue
                    except RuntimeError as exc:
                        websocket.send_json(
                            build_error_message_fn(
                                "session-error", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue
                    session = new_session
                    active_sessions[session_id] = session
                    websocket.send_json(
                        build_event_message_fn(
                            event,
                            session,
                            session_id=session_id,
                        ).model_dump(mode="json")
                    )
                    continue

                if message_type == "transcript":
                    websocket.send_json(
                        build_transcript_message_fn(session_id, session).model_dump(
                            mode="json"
                        )
                    )
                    continue

                if message_type == "clear_transcript":
                    session.clear_transcript()
                    websocket.send_json(
                        build_transcript_message_fn(session_id, session).model_dump(
                            mode="json"
                        )
                    )
                    continue

                websocket.send_json(
                    build_error_message_fn(
                        "unknown-message", f"Unsupported message type '{message_type}'."
                    ).model_dump(mode="json")
                )

        finally:
            active_sessions.pop(session_id, None)

    return router
