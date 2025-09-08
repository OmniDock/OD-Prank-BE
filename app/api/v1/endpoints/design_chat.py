"""
Design Chat WebSocket endpoint for interactive scenario design
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException
from fastapi.responses import JSONResponse
from typing import Dict, Any, Optional
import json
import uuid

from app.core.auth import get_current_user, AuthUser
from app.core.database import AsyncSession, get_db_session
from app.langchain.processors.design_chat_processor import DesignChatProcessor
from app.langchain.state import DesignChatState
from app.services.cache_service import CacheService
from app.core.logging import console_logger

router = APIRouter()


async def get_current_user_ws(websocket: WebSocket) -> Optional[AuthUser]:
    """
    Extract and validate user from WebSocket connection
    """
    try:
        # Try to get token from query params
        token = websocket.query_params.get("token")
        if not token:
            # Try to get from headers
            auth_header = websocket.headers.get("authorization", "")
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]
        
        if not token:
            await websocket.close(code=1008, reason="No authentication token")
            return None
        
        # Validate token using existing auth system
        from app.core.auth import verify_jwt_token, AuthUser
        payload = await verify_jwt_token(token)
        
        # Create AuthUser from payload
        user = AuthUser(
            user_id=payload.get("sub"),
            email=payload.get("email"),
            metadata=payload.get("user_metadata", {})
        )
        return user
        
    except Exception as e:
        console_logger.error(f"WebSocket auth failed: {str(e)}")
        await websocket.close(code=1008, reason="Authentication failed")
        return None


@router.websocket("/ws")
async def design_chat_websocket(websocket: WebSocket):
    """
    WebSocket endpoint for interactive design chat
    
    Message format:
    Inbound:
        - {"type": "message", "content": "user message"}
        - {"type": "finalize"}
        
    Outbound:
        - {"type": "response", "suggestion": "...", "draft": "..."}
        - {"type": "finalized", "description": "..."}
        - {"type": "error", "message": "..."}
    """
    await websocket.accept()
    
    # Authenticate user
    user = await get_current_user_ws(websocket)
    if not user:
        return
    
    console_logger.debug(f"Design chat started for user {user.id}")
    
    processor = DesignChatProcessor()
    cache = await CacheService.get_global()
    session_id = str(uuid.uuid4())
    
    # Initialize state
    state = DesignChatState()
    # Load per-user persisted state if available
    try:
        persisted_state = await cache.get_json(f"design_chat:user:{user.id_str}")
        if isinstance(persisted_state, dict):
            state = DesignChatState(**persisted_state)
            console_logger.debug(f"WS[{session_id}] restored persisted design chat state for user {user.id}")
    except Exception as _e:
        # Non-fatal: continue with fresh state
        console_logger.debug(f"WS[{session_id}] no persisted state or failed to load: {_e}")
    
    try:
        # Send initial greeting only if there is no existing chat history
        if not getattr(state, "messages", []):
            await websocket.send_json({
                "type": "response",
                "suggestion": "Wie kann ich dir beim Verfeinern helfen? Beschreibe deine Prank-Idee. \n Du kannst jederzeit auf 'Szenario erstellen' klicken um es zu generieren.",
                "draft": ""
            })
            console_logger.debug(f"WS[{session_id}] sent greeting: suggestion='Wie kann ich dir beim Verfeinern helfen?...' draft_len=0")
        else:
            console_logger.debug(f"WS[{session_id}] restored chat exists; skipping greeting (messages={len(state.messages)})")
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message = json.loads(data)
            
            if message.get("type") == "message":
                # Add user message to state
                state.messages.append({
                    "role": "user",
                    "content": message.get("content", "")
                })
                
                # Send typing indicator
                await websocket.send_json({
                    "type": "typing",
                    "status": "start"
                })
                
                # Stream the processing for real-time updates
                partial_suggestion = ""
                last_suggestion = ""
                async for event in processor.stream(state):
                    # Check if we have a partial suggestion update
                    if isinstance(event, dict):
                        for node_name, node_data in event.items():
                            if node_name == "suggest" and isinstance(node_data, dict) and "next_suggestion" in node_data:
                                # Send partial suggestion as it's being generated
                                suggestion_chunk = node_data.get("next_suggestion", "")
                                if suggestion_chunk and suggestion_chunk != partial_suggestion:
                                    await websocket.send_json({
                                        "type": "stream",
                                        "content": suggestion_chunk[len(partial_suggestion):],
                                        "node": node_name
                                    })
                                    partial_suggestion = suggestion_chunk
                                    last_suggestion = suggestion_chunk
                            
                            # Update state with node results
                            if isinstance(node_data, dict):
                                for key, value in node_data.items():
                                    if value is not None and hasattr(state, key):
                                        setattr(state, key, value)
                
                # Cache the state for potential recovery
                await cache.set_json(
                    f"design_chat:{session_id}",
                    {
                        "user_id": str(user.id),
                        "state": state.model_dump()
                    },
                    ttl=1800  # 30 minutes
                )
                
                # Send final response
                # Ensure we always send a non-empty suggestion
                suggestion_out = last_suggestion or partial_suggestion
                if not suggestion_out:
                    suggestion_out = (
                        "Alles klar! Was fehlt dir noch? (Wenn du fertig bist, klicke auf 'Szenario erstellen'.)"
                        if getattr(state, "scenario", "") else
                        "Was für einen Prank hast du im Kopf? (Wenn du fertig bist, klicke auf 'Szenario erstellen'.)"
                    )
                response = {
                    "type": "response",
                    "suggestion": suggestion_out,
                    "draft": getattr(state, "scenario", "")
                }
                
                await websocket.send_json(response)
                console_logger.debug(f"WS[{session_id}] sent response: suggestion='{response['suggestion'][:80]}...' draft_len={len(response.get('draft') or '')}")
                
                # Append assistant turn to backend message history
                if response.get("suggestion"):
                    state.messages.append({
                        "role": "assistant",
                        "content": response["suggestion"]
                    })
                
                # Persist per-user chat state (ephemeral)
                try:
                    await cache.set_json(
                        f"design_chat:user:{user.id_str}",
                        state.model_dump(),
                        ttl=3600
                    )
                except Exception as _e:
                    console_logger.debug(f"WS[{session_id}] failed to persist state for user {user.id}: {_e}")
                
            elif message.get("type") == "finalize":
                # User wants to generate the scenario - let them decide when it's ready
                await websocket.send_json({
                    "type": "finalized",
                    "description": getattr(state, "scenario", "") or ""
                })
                # Clear per-user persisted state on finalize
                try:
                    await cache.delete(f"design_chat:user:{user.id_str}")
                except Exception:
                    pass
                break
                
            elif message.get("type") == "reset":
                # Explicit reset from user
                state = DesignChatState()
                try:
                    await cache.delete(f"design_chat:user:{user.id_str}")
                except Exception:
                    pass
                await websocket.send_json({"type": "reset", "status": "cleared"})
                
            elif message.get("type") == "ping":
                # Keep-alive ping
                await websocket.send_json({"type": "pong"})
                
    except WebSocketDisconnect:
        console_logger.debug(f"Design chat disconnected for user {user.id}")
    except Exception as e:
        console_logger.error(f"Design chat error: {str(e)}")
        try:
            await websocket.send_json({
                "type": "error",
                "message": f"Chat error: {str(e)}"
            })
        except:
            pass
    finally:
        # Clean up cache
        await cache.delete(f"design_chat:{session_id}")


@router.post("/session/restore")
async def restore_chat_session(
    session_id: str,
    user: AuthUser = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session)
) -> Dict[str, Any]:
    """
    Restore a previous chat session if it exists
    """
    cache = await CacheService.get_global()
    
    cached = await cache.get_json(f"design_chat:{session_id}")
    if not cached:
        raise HTTPException(status_code=404, detail="Session not found")
    
    if cached.get("user_id") != str(user.id):
        raise HTTPException(status_code=403, detail="Not authorized")
    
    return {
        "status": "restored",
        "state": cached["state"]
    }


@router.get("/history")
async def get_user_design_chat_history(
    user: AuthUser = Depends(get_current_user)
) -> Dict[str, Any]:
    cache = await CacheService.get_global()
    state = await cache.get_json(f"design_chat:user:{user.id_str}")
    return {"state": state or DesignChatState().model_dump()}


@router.delete("/history")
async def clear_user_design_chat_history(
    user: AuthUser = Depends(get_current_user)
) -> Dict[str, str]:
    cache = await CacheService.get_global()
    await cache.delete(f"design_chat:user:{user.id_str}")
    return {"status": "cleared"}
