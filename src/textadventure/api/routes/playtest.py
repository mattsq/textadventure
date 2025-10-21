"""Playtest routes for WebSocket-based adventure testing and transcripts."""

from __future__ import annotations

import uuid
from typing import Callable, Any

from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from ..models import (
    PlaytestTranscriptResponse,
)


def create_playtest_router(
    playtest_manager: Any,
    active_sessions: dict[str, Any],
    *,
    build_transcript_entries_fn: Callable[..., Any],
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
    async def playtest_endpoint(websocket: WebSocket) -> None:
        await websocket.accept()

        initial_project_id = websocket.query_params.get("project_id")

        session_id = uuid.uuid4().hex

        try:
            try:
                session = playtest_manager.create_session(project_id=initial_project_id)
                initial_event = session.reset()
            except FileNotFoundError as exc:
                await websocket.send_json(
                    build_error_message_fn("project-not-found", str(exc)).model_dump(
                        mode="json"
                    )
                )
                await websocket.close(code=4404)
                return
            except ValueError as exc:
                await websocket.send_json(
                    build_error_message_fn("invalid-project", str(exc)).model_dump(
                        mode="json"
                    )
                )
                await websocket.close(code=4400)
                return
            except RuntimeError as exc:
                await websocket.send_json(
                    build_error_message_fn("session-error", str(exc)).model_dump(
                        mode="json"
                    )
                )
                await websocket.close(code=4500)
                return

            active_sessions[session_id] = session

            await websocket.send_json(
                build_event_message_fn(
                    initial_event,
                    session_id=session_id,
                    instruction_hint="send_command",
                ).model_dump(mode="json")
            )

            while True:
                payload = await websocket.receive_json()
                message_type = payload.get("type")

                if message_type == "send_command":
                    command = payload.get("command")
                    if not isinstance(command, str):
                        await websocket.send_json(
                            build_error_message_fn(
                                "invalid-payload",
                                "Expected 'command' to be a string.",
                            ).model_dump(mode="json")
                        )
                        continue

                    try:
                        event = session.send_command(command)
                    except ValueError as exc:
                        await websocket.send_json(
                            build_error_message_fn(
                                "invalid-command", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue

                    await websocket.send_json(
                        build_event_message_fn(
                            event,
                            session_id=session_id,
                            instruction_hint="send_command",
                        ).model_dump(mode="json")
                    )

                elif message_type == "reset":
                    try:
                        event = session.reset()
                    except RuntimeError as exc:
                        await websocket.send_json(
                            build_error_message_fn("reset-error", str(exc)).model_dump(
                                mode="json"
                            )
                        )
                        continue

                    await websocket.send_json(
                        build_event_message_fn(
                            event,
                            session_id=session_id,
                            instruction_hint="send_command",
                        ).model_dump(mode="json")
                    )

                elif message_type == "switch_project":
                    project_id = payload.get("project_id")
                    if not isinstance(project_id, str):
                        await websocket.send_json(
                            build_error_message_fn(
                                "invalid-payload",
                                "Expected 'project_id' to be a string.",
                            ).model_dump(mode="json")
                        )
                        continue

                    try:
                        new_session = playtest_manager.create_session(
                            project_id=project_id
                        )
                        event = new_session.reset()
                    except FileNotFoundError as exc:
                        await websocket.send_json(
                            build_error_message_fn(
                                "project-not-found", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue
                    except ValueError as exc:
                        await websocket.send_json(
                            build_error_message_fn(
                                "invalid-project", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue
                    except RuntimeError as exc:
                        await websocket.send_json(
                            build_error_message_fn(
                                "session-error", str(exc)
                            ).model_dump(mode="json")
                        )
                        continue

                    # Replace the active session
                    active_sessions[session_id] = new_session
                    session = new_session

                    await websocket.send_json(
                        build_event_message_fn(
                            event,
                            session_id=session_id,
                            instruction_hint="send_command",
                        ).model_dump(mode="json")
                    )

                else:
                    await websocket.send_json(
                        build_error_message_fn(
                            "unknown-message-type",
                            f"Unsupported message type: {message_type}",
                        ).model_dump(mode="json")
                    )

        except WebSocketDisconnect:
            pass
        finally:
            active_sessions.pop(session_id, None)

    return router
