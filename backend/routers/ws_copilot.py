import asyncio
import base64
import io
import json
import logging
import os
import time
from typing import Dict, List, Optional
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage

from config import settings
from agent.graph import execute_agent_workflow
from audio.tts_engine import stream_text_to_audio, select_neural_voice, is_marathi_or_devanagari
from app.core.security import decode_websocket_ticket

logger = logging.getLogger("copilot.ws")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")

router = APIRouter()

# Global async redis connection pool reference
redis_client: Optional[aioredis.Redis] = None

# In-memory buffer for streaming audio chunks per active session
session_audio_buffers: Dict[str, List[bytes]] = {}
session_audio_mimes: Dict[str, str] = {}


async def get_redis_client() -> aioredis.Redis:
    global redis_client
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if redis_client is not None:
        client_loop = getattr(redis_client.connection_pool, "_loop", None)
        if client_loop is not None and client_loop is not current_loop:
            redis_client = None

    if redis_client is None:
        redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
            socket_connect_timeout=2.0
        )
    return redis_client


@router.websocket("/ws/copilot")
@router.websocket("/ws/copilot/{session_id}")
async def websocket_copilot_endpoint(
    websocket: WebSocket,
    session_id: Optional[str] = None,
    ticket: Optional[str] = None,
):
    """
    Asynchronous WebSocket endpoint for Real-Time Multimodal Voice & Support Copilot.
    Pipeline:
    1. Origin header verification against allowed CORS origins
    2. Short-lived signed session ticket verification (cryptographic bind)
    3. Low-latency ping-pong heartbeat
    4. Live 16kHz audio chunk streaming from client microphone
    5. End-of-speech assembly and Whisper STT via Groq
    6. LangGraph multi-turn LLM reasoning with tenant-scoped tool policy
    7. Streaming Microsoft Edge Neural TTS audio packets (MP3) back to client
    8. End-to-End Latency Waterfall Telemetry (STT, LLM, TTS, E2E)
    9. Tenant-isolated Redis conversational memory retention & state sync
    """
    # 1. Validate Origin header if present
    origin = websocket.headers.get("origin")
    if origin:
        allowed = [o.rstrip("/") for o in settings.CORS_ALLOWED_ORIGINS]
        if origin.rstrip("/") not in allowed and origin != "null":
            logger.warning(f"WebSocket handshake rejected: unauthorized origin '{origin}'")
            await websocket.close(code=4003, reason="Unauthorized origin")
            return

    # 2. Extract and validate session ticket
    ticket_val = ticket or websocket.query_params.get("ticket")
    if not ticket_val:
        logger.warning(f"WebSocket handshake rejected: missing session ticket for session {session_id}")
        await websocket.close(code=4401, reason="Missing session ticket")
        return

    try:
        ticket_payload = decode_websocket_ticket(ticket_val)
    except ValueError as err:
        logger.warning(f"WebSocket handshake rejected: ticket validation failed ({err})")
        await websocket.close(code=4401, reason=str(err))
        return

    ticket_session_id = ticket_payload.get("session_id")
    if session_id and session_id != ticket_session_id:
        logger.warning(
            f"WebSocket handshake rejected: path session_id '{session_id}' != ticket session_id '{ticket_session_id}'"
        )
        await websocket.close(code=4401, reason="Mismatched session ID")
        return

    session_id = ticket_session_id
    tenant_id = ticket_payload.get("tenant_id")
    tenant_slug = ticket_payload.get("tenant_slug", "sai-smile")
    session_type = ticket_payload.get("session_type", "public")
    allowed_tools = set(ticket_payload.get("allowed_tools", []))

    await websocket.accept()
    logger.info(f"WebSocket client connected: session_id={session_id}, tenant={tenant_slug}, type={session_type}")
    session_audio_buffers[session_id] = []
    session_audio_mimes[session_id] = "audio/webm"

    tenant_key_prefix = f"copilot:tenant:{tenant_id}:session:{session_id}"

    # Ping Redis and load existing session transcripts & telemetry if available
    redis_status = "unavailable"
    existing_transcripts = []
    last_telemetry = None
    try:
        r = await get_redis_client()
        pong = await r.ping()
        if pong:
            redis_status = "connected"
            await r.set(f"{tenant_key_prefix}:connected_at", str(time.time()), ex=86400)
            raw_list = await r.lrange(f"{tenant_key_prefix}:transcript", -50, -1)
            if len(raw_list) == 0:
                raw_list = await r.lrange(f"copilot:session:{session_id}:transcript", -50, -1)
            for item in raw_list:
                try:
                    existing_transcripts.append(json.loads(item))
                except Exception:
                    pass
            raw_telem = await r.get(f"{tenant_key_prefix}:last_telemetry")
            if not raw_telem:
                raw_telem = await r.get(f"copilot:session:{session_id}:last_telemetry")
            if raw_telem:
                try:
                    last_telemetry = json.loads(raw_telem)
                except Exception:
                    pass
            logger.info(f"Redis verified for session {session_id}. Loaded {len(existing_transcripts)} cached items.")
    except Exception as e:
        logger.warning(f"Redis ping/load failed for session {session_id}: {e}")
        redis_status = f"disconnected ({str(e)})"

    groq_ready = bool(settings.GROQ_API_KEY)

    # Send connection acknowledgement
    await websocket.send_json({
        "type": "connection_ack",
        "session_id": session_id,
        "redis_status": redis_status,
        "groq_configured": groq_ready,
        "model": settings.GROQ_MODEL,
        "llm_model": settings.LLM_MODEL,
        "tts_voice": settings.TTS_VOICE,
        "tts_voice_mr": settings.TTS_VOICE_MR,
        "supported_languages": ["mr", "en"],
        "transcripts": existing_transcripts,
        "last_telemetry": last_telemetry,
        "timestamp": time.time(),
        "message": "Connected to Real-Time Voice Copilot Multimodal Engine (Bilingual Marathi & English)"
    })

    async def stream_tts_to_client(text: str) -> tuple[int, int]:
        """
        Streams synthesized neural speech MP3 chunks over WebSocket with automatic
        language-aware voice selection (Marathi: mr-IN-AarohiNeural, English: en-US-ChristopherNeural).
        Returns: (tts_duration_ms, tts_first_chunk_ms)
        """
        if not text:
            return 0, 0
        tts_start = time.perf_counter()
        first_chunk_ms = None
        chunk_count = 0
        chosen_voice = select_neural_voice(
            text,
            default_voice=settings.TTS_VOICE_EN,
            marathi_voice=settings.TTS_VOICE_MR
        )
        is_mr = is_marathi_or_devanagari(text)

        try:
            await websocket.send_json({
                "type": "audio_stream_start",
                "format": "mp3",
                "voice": chosen_voice,
                "language": "mr" if is_mr else "en",
                "session_id": session_id,
                "timestamp": time.time()
            })

            async for audio_chunk in stream_text_to_audio(text, voice=chosen_voice):
                if first_chunk_ms is None:
                    first_chunk_ms = round((time.perf_counter() - tts_start) * 1000)
                b64_chunk = base64.b64encode(audio_chunk).decode("utf-8")
                chunk_count += 1
                await websocket.send_json({
                    "type": "audio_stream_chunk",
                    "data": b64_chunk,
                    "session_id": session_id,
                    "index": chunk_count
                })

            tts_duration_ms = round((time.perf_counter() - tts_start) * 1000)
            if first_chunk_ms is None:
                first_chunk_ms = tts_duration_ms

            await websocket.send_json({
                "type": "audio_stream_end",
                "session_id": session_id,
                "voice": chosen_voice,
                "language": "mr" if is_mr else "en",
                "total_chunks": chunk_count,
                "latency_ms": tts_duration_ms,
                "first_chunk_ms": first_chunk_ms,
                "timestamp": time.time()
            })
            logger.info(f"Streamed {chunk_count} TTS audio chunks [{chosen_voice}] in {tts_duration_ms}ms (first chunk {first_chunk_ms}ms)")
            return tts_duration_ms, first_chunk_ms
        except Exception as tts_err:
            logger.error(f"Error streaming TTS to session {session_id}: {tts_err}")
            return 0, 0

    async def run_langgraph_for_user_input(
        user_text: str,
        stt_ms: int = 0,
        turn_start_time: Optional[float] = None
    ):
        """Helper to invoke LangGraph agent, stream tool events, stream TTS, and emit Latency Waterfall."""
        # 1. Fetch conversation history from Redis
        history_messages: List[BaseMessage] = []
        try:
            r = await get_redis_client()
            raw_turns = await r.lrange(f"{tenant_key_prefix}:messages", -10, -1)
            if len(raw_turns) == 0:
                raw_turns = await r.lrange(f"copilot:session:{session_id}:messages", -10, -1)
            for raw_m in raw_turns:
                m_data = json.loads(raw_m)
                if m_data.get("role") == "user":
                    history_messages.append(HumanMessage(content=m_data.get("content", "")))
                elif m_data.get("role") == "assistant":
                    history_messages.append(AIMessage(content=m_data.get("content", "")))
        except Exception as r_err:
            logger.warning(f"Failed to read conversation memory from Redis: {r_err}")

        # Append current user prompt
        history_messages.append(HumanMessage(content=user_text))

        # 2. Event emitter callback for WebSocket streaming
        async def emit_agent_event(event_data: dict):
            try:
                await websocket.send_json(event_data)
            except Exception as send_err:
                logger.error(f"Failed to send agent event to client: {send_err}")

        # 3. Execute LangGraph workflow with scoped allowed_tools
        llm_start = time.perf_counter()
        assistant_reply, tools_used = await execute_agent_workflow(
            messages=history_messages,
            session_id=session_id,
            emit_event=emit_agent_event,
            allowed_tools=list(allowed_tools) if allowed_tools else None
        )
        llm_reasoning_ms = round((time.perf_counter() - llm_start) * 1000)

        # 4. Save to Redis conversation memory (tenant-isolated)
        try:
            r = await get_redis_client()
            await r.rpush(
                f"{tenant_key_prefix}:messages",
                json.dumps({"role": "user", "content": user_text, "timestamp": time.time()}, ensure_ascii=False)
            )
            await r.rpush(
                f"{tenant_key_prefix}:messages",
                json.dumps({"role": "assistant", "content": assistant_reply, "timestamp": time.time()}, ensure_ascii=False)
            )
            await r.expire(f"{tenant_key_prefix}:messages", 86400)

            assistant_transcript_item = {
                "id": f"ai_{int(time.time() * 1000)}",
                "session_id": session_id,
                "text": assistant_reply,
                "role": "assistant",
                "tools_used": tools_used,
                "timestamp": time.time(),
                "model": settings.LLM_MODEL
            }
            await r.rpush(f"{tenant_key_prefix}:transcript", json.dumps(assistant_transcript_item, ensure_ascii=False))
            await r.expire(f"{tenant_key_prefix}:transcript", 86400)
        except Exception as save_err:
            logger.warning(f"Failed to persist conversation turns in Redis: {save_err}")

        # 5. Phase 4: Stream Neural TTS audio back to frontend
        tts_ms, tts_first_chunk_ms = 0, 0
        if assistant_reply:
            tts_ms, tts_first_chunk_ms = await stream_tts_to_client(assistant_reply)

        # 6. Phase 5: Calculate End-to-End Latency Waterfall
        if turn_start_time:
            total_e2e_ms = round((time.perf_counter() - turn_start_time) * 1000)
        else:
            total_e2e_ms = stt_ms + llm_reasoning_ms + tts_ms

        telemetry_metrics = {
            "stt_ms": stt_ms,
            "llm_reasoning_ms": llm_reasoning_ms,
            "tts_first_chunk_ms": tts_first_chunk_ms or tts_ms,
            "tts_ms": tts_ms,
            "total_e2e_ms": total_e2e_ms,
            "tools_count": len(tools_used),
            "timestamp": time.time()
        }

        # Cache telemetry in Redis (tenant-isolated)
        try:
            r = await get_redis_client()
            await r.set(f"{tenant_key_prefix}:last_telemetry", json.dumps(telemetry_metrics), ex=86400)
            await r.rpush(f"{tenant_key_prefix}:latencies", json.dumps(telemetry_metrics))
            await r.ltrim(f"{tenant_key_prefix}:latencies", -50, -1)
        except Exception as telem_err:
            logger.warning(f"Failed to store telemetry in Redis: {telem_err}")

        # Emit structured latency telemetry to client
        await websocket.send_json({
            "type": "latency_telemetry",
            "session_id": session_id,
            "metrics": telemetry_metrics,
            "timestamp": time.time()
        })
        logger.info(f"Latency Waterfall: STT={stt_ms}ms, LLM={llm_reasoning_ms}ms, TTS={tts_ms}ms, Total E2E={total_e2e_ms}ms")

    try:
        while True:
            raw_text = await websocket.receive_text()
            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                logger.warning(f"Received non-JSON payload from session {session_id}")
                await websocket.send_json({
                    "type": "error",
                    "error": "Invalid JSON format",
                    "timestamp": time.time()
                })
                continue

            msg_type = data.get("type")

            # -------------------------------------------------------------
            # 1. PING - PONG HEARTBEAT
            # -------------------------------------------------------------
            if msg_type == "ping":
                client_sent_time = data.get("timestamp")
                current_time = time.time()
                response_payload = {
                    "type": "pong",
                    "timestamp": current_time,
                    "session_id": session_id,
                    "client_timestamp": client_sent_time,
                }
                try:
                    r = await get_redis_client()
                    await r.set(f"{tenant_key_prefix}:last_ping", str(current_time), ex=3600)
                except Exception:
                    pass
                await websocket.send_json(response_payload)

            # -------------------------------------------------------------
            # 2. AUDIO CHUNK STREAMING (Live microphone audio)
            # -------------------------------------------------------------
            elif msg_type == "audio_chunk":
                base64_data = data.get("data")
                mime_type = data.get("mime_type", "audio/webm")
                if base64_data:
                    try:
                        chunk_bytes = base64.b64decode(base64_data)
                        if session_id not in session_audio_buffers:
                            session_audio_buffers[session_id] = []
                        session_audio_buffers[session_id].append(chunk_bytes)
                        session_audio_mimes[session_id] = mime_type
                    except Exception as b64_err:
                        logger.error(f"Error decoding base64 audio chunk: {b64_err}")

            # -------------------------------------------------------------
            # 3. AUDIO STREAM END -> ASSEMBLE, STT, LANGGRAPH, TTS & TELEMETRY
            # -------------------------------------------------------------
            elif msg_type == "audio_end":
                turn_start_time = time.perf_counter()
                mime_type = data.get("mime_type") or session_audio_mimes.get(session_id, "audio/webm")

                # Check if client sent intact complete audio blob as base64 in data
                raw_b64 = data.get("data")
                if raw_b64 and isinstance(raw_b64, str):
                    try:
                        complete_audio = base64.b64decode(raw_b64)
                        logger.info(f"Decoded complete intact audio payload ({len(complete_audio)} bytes) from audio_end packet")
                    except Exception as dec_err:
                        logger.warning(f"Failed to decode base64 audio in audio_end: {dec_err}")
                        chunks = session_audio_buffers.pop(session_id, [])
                        complete_audio = b"".join(chunks)
                else:
                    chunks = session_audio_buffers.pop(session_id, [])
                    complete_audio = b"".join(chunks)

                session_audio_buffers[session_id] = []
                total_bytes = len(complete_audio)
                logger.info(f"Received audio_end for session {session_id}: {total_bytes} bytes (mime: {mime_type})")

                # Guard against empty or tiny audio payloads (< 2000 bytes prevents Groq 400 invalid_media_file)
                if total_bytes < 2000:
                    logger.warning(f"Audio buffer too small ({total_bytes} bytes < 2000) for session {session_id}. Skipping Groq Whisper call.")
                    await websocket.send_json({
                        "type": "stt_error",
                        "error": "Audio stream was too brief or empty. Please speak for at least one second.",
                        "timestamp": time.time()
                    })
                    continue

                await websocket.send_json({
                    "type": "stt_status",
                    "status": "transcribing",
                    "audio_bytes": total_bytes,
                    "timestamp": time.time()
                })

                stt_start_time = time.perf_counter()
                transcribed_text = ""
                is_demo = False
                stt_model = settings.GROQ_MODEL

                # Standardize clean MIME and file extension
                clean_mime = "audio/webm"
                ext = "webm"
                lower_mime = (mime_type or "").lower()
                if "mp4" in lower_mime or "m4a" in lower_mime:
                    clean_mime = "audio/mp4"
                    ext = "m4a"
                elif "mp3" in lower_mime or "mpeg" in lower_mime:
                    clean_mime = "audio/mpeg"
                    ext = "mp3"
                elif "wav" in lower_mime:
                    clean_mime = "audio/wav"
                    ext = "wav"
                elif "ogg" in lower_mime:
                    clean_mime = "audio/ogg"
                    ext = "ogg"
                elif "webm" in lower_mime:
                    clean_mime = "audio/webm"
                    ext = "webm"

                filename = f"audio_{session_id}.{ext}"
                groq_api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")

                if groq_api_key:
                    try:
                        from groq import AsyncGroq
                        client = AsyncGroq(api_key=groq_api_key)
                        audio_bio = io.BytesIO(complete_audio)
                        audio_bio.name = filename

                        marathi_clinical_prompt = (
                            "नमस्कार, मला दात स्वच्छ करणे, क्लिनिंग, रूट कॅनल, दात काढणे, "
                            "डॉक्टर तपासणी, अपॉइंटमेंट बुक करणे, फी किती आहे, वेळ मिळेल का."
                        )

                        transcription_kwargs = {
                            "file": (filename, audio_bio, clean_mime),
                            "model": settings.GROQ_MODEL,
                            "temperature": 0.0,
                            "prompt": marathi_clinical_prompt,
                        }
                        req_lang = str(data.get("language") or "").lower().strip()
                        if req_lang in ["mr", "marathi"]:
                            # Strongly enforce language="mr" when Marathi is selected
                            transcription_kwargs["language"] = "mr"
                            transcription_kwargs["prompt"] = marathi_clinical_prompt
                        elif req_lang in ["en", "english"]:
                            transcription_kwargs["language"] = "en"
                            transcription_kwargs["prompt"] = (
                                "Sai Smile Dental Clinic, dental cleaning, root canal therapy, "
                                "teeth whitening, consultation fee, doctor appointment booking."
                            )
                        elif req_lang in ["hi", "hindi"]:
                            transcription_kwargs["language"] = "hi"
                        else:
                            # Default / Auto: keep clinical Marathi prompt to bias phonetic decoding
                            transcription_kwargs["prompt"] = marathi_clinical_prompt

                        transcription = await client.audio.transcriptions.create(**transcription_kwargs)
                        transcribed_text = (transcription.text or "").strip()
                        logger.info(f"Groq Whisper transcription success for {session_id} [lang={req_lang or 'auto'}]: '{transcribed_text}'")
                    except Exception as stt_err:
                        logger.error(f"Groq Whisper STT call failed for session {session_id}: {stt_err}", exc_info=True)
                        await websocket.send_json({
                            "type": "stt_error",
                            "error": f"Transcription error: {str(stt_err)}",
                            "timestamp": time.time()
                        })
                        continue
                else:
                    is_demo = True
                    stt_model = "mock-fallback"
                    transcribed_text = (
                        f"[Speech Detected] Captured {total_bytes:,} bytes of voice audio. "
                        f"Add GROQ_API_KEY to backend/.env to enable instant Whisper-Large-v3 transcription."
                    )

                if not transcribed_text:
                    logger.info(f"Groq Whisper returned empty text for session {session_id}")
                    await websocket.send_json({
                        "type": "stt_error",
                        "error": "Could not detect clear speech. Please hold the button and speak clearly.",
                        "timestamp": time.time()
                    })
                    continue

                stt_latency_ms = round((time.perf_counter() - stt_start_time) * 1000)

                user_transcript_item = {
                    "id": f"tx_{int(time.time() * 1000)}",
                    "session_id": session_id,
                    "text": transcribed_text,
                    "role": "user",
                    "latency_ms": stt_latency_ms,
                    "audio_bytes": total_bytes,
                    "timestamp": time.time(),
                    "model": stt_model,
                    "is_demo": is_demo
                }

                try:
                    r = await get_redis_client()
                    await r.rpush(f"{tenant_key_prefix}:transcript", json.dumps(user_transcript_item, ensure_ascii=False))
                    await r.expire(f"{tenant_key_prefix}:transcript", 86400)
                    await r.set(f"{tenant_key_prefix}:last_speech", str(time.time()), ex=86400)
                except Exception as r_err:
                    logger.warning(f"Failed to cache user transcript in Redis: {r_err}")

                await websocket.send_json({
                    "type": "transcription",
                    **user_transcript_item
                })

                if transcribed_text and not transcribed_text.startswith("[Whisper STT Error"):
                    await run_langgraph_for_user_input(
                        user_text=transcribed_text,
                        stt_ms=stt_latency_ms,
                        turn_start_time=turn_start_time
                    )

            # -------------------------------------------------------------
            # 4. DIRECT TEXT INPUT
            # -------------------------------------------------------------
            elif msg_type == "user_text":
                turn_start_time = time.perf_counter()
                user_text = data.get("text", "").strip()
                if user_text:
                    user_transcript_item = {
                        "id": f"tx_{int(time.time() * 1000)}",
                        "session_id": session_id,
                        "text": user_text,
                        "role": "user",
                        "timestamp": time.time(),
                        "model": "text-input"
                    }
                    try:
                        r = await get_redis_client()
                        await r.rpush(f"{tenant_key_prefix}:transcript", json.dumps(user_transcript_item, ensure_ascii=False))
                    except Exception:
                        pass

                    await websocket.send_json({
                        "type": "transcription",
                        **user_transcript_item
                    })

                    await run_langgraph_for_user_input(
                        user_text=user_text,
                        stt_ms=0,
                        turn_start_time=turn_start_time
                    )

            # -------------------------------------------------------------
            # 5. INDEPENDENT TTS TEST
            # -------------------------------------------------------------
            elif msg_type == "test_tts":
                test_text = data.get("text", "Hello! This is your Voice Copilot powered by Microsoft Edge Neural Speech.")
                await stream_tts_to_client(test_text)

            # -------------------------------------------------------------
            # 6. CLEAR TRANSCRIPTS & MEMORY
            # -------------------------------------------------------------
            elif msg_type == "clear_transcripts":
                try:
                    r = await get_redis_client()
                    await r.delete(f"{tenant_key_prefix}:transcript")
                    await r.delete(f"{tenant_key_prefix}:messages")
                    await r.delete(f"{tenant_key_prefix}:latencies")
                    await r.delete(f"{tenant_key_prefix}:last_telemetry")
                    # Clear legacy keys as well
                    await r.delete(f"copilot:session:{session_id}:transcript")
                    await r.delete(f"copilot:session:{session_id}:messages")
                    await r.delete(f"copilot:session:{session_id}:latencies")
                    await r.delete(f"copilot:session:{session_id}:last_telemetry")
                    await websocket.send_json({
                        "type": "transcripts_cleared",
                        "session_id": session_id,
                        "timestamp": time.time()
                    })
                    logger.info(f"Cleared transcripts, memory, and telemetry for session {session_id}")
                except Exception as e:
                    logger.error(f"Failed to clear transcripts: {e}")

            # -------------------------------------------------------------
            # 7. OTHER PACKETS
            # -------------------------------------------------------------
            else:
                await websocket.send_json({
                    "type": "echo",
                    "original_type": msg_type,
                    "received": data,
                    "timestamp": time.time()
                })

    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected gracefully: session_id={session_id}")
        session_audio_buffers.pop(session_id, None)
        session_audio_mimes.pop(session_id, None)
    except Exception as e:
        logger.error(f"Unexpected error in WebSocket session {session_id}: {e}", exc_info=True)
        session_audio_buffers.pop(session_id, None)
        session_audio_mimes.pop(session_id, None)
        try:
            await websocket.close(code=1011)
        except Exception:
            pass
