import logging
import re
from typing import AsyncGenerator, Optional
import edge_tts

logger = logging.getLogger("copilot.tts")

DEFAULT_VOICE = "en-US-ChristopherNeural"
MARATHI_VOICE_FEMALE = "mr-IN-AarohiNeural"
MARATHI_VOICE_MALE = "mr-IN-ManoharNeural"


def is_marathi_or_devanagari(text: str) -> bool:
    """
    Checks if the text contains Devanagari/Marathi characters (U+0900 to U+097F).
    """
    if not text:
        return False
    return any(0x0900 <= ord(c) <= 0x097F for c in text)


def select_neural_voice(
    text: str,
    default_voice: str = DEFAULT_VOICE,
    marathi_voice: str = MARATHI_VOICE_FEMALE
) -> str:
    """
    Dynamically selects the appropriate neural voice:
    - If text contains Devanagari/Marathi characters, routes to high-fidelity Marathi voice ('mr-IN-AarohiNeural').
    - Otherwise uses English neural voice ('en-US-ChristopherNeural').
    """
    if is_marathi_or_devanagari(text):
        return marathi_voice
    return default_voice


def clean_text_for_speech(text: str) -> str:
    """
    Strips markdown formatting, bold/italics, code blocks, and excessive symbols
    to ensure smooth, natural neural speech delivery.
    """
    if not text:
        return ""

    # Remove code blocks
    cleaned = re.sub(r"```[\s\S]*?```", " [code snippet omitted] ", text)
    # Remove inline code backticks
    cleaned = re.sub(r"`(.*?)`", r"\1", cleaned)
    # Remove markdown bold/italics
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)
    # Remove markdown headers
    cleaned = re.sub(r"^#+\s*", "", cleaned, flags=re.MULTILINE)
    # Remove markdown list bullets and numbers
    cleaned = re.sub(r"^\s*[-*+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    # Replace URLs
    cleaned = re.sub(r"https?://\S+", "web link", cleaned)
    # Clean multiple spaces and newlines
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


async def stream_text_to_audio(
    text: str,
    voice: Optional[str] = None,
    rate: str = "+0%",
    pitch: str = "+0Hz"
) -> AsyncGenerator[bytes, None]:
    """
    Asynchronously streams synthesized MP3 audio chunks using Microsoft Neural TTS (Edge TTS).
    Zero cost, high fidelity, ultra-low latency with automatic Marathi/English language routing.
    """
    clean_text = clean_text_for_speech(text)
    if not clean_text:
        return

    chosen_voice = voice if voice else select_neural_voice(clean_text)
    logger.info(f"Synthesizing speech with voice '{chosen_voice}' for: '{clean_text[:60]}...'")

    try:
        communicate = edge_tts.Communicate(clean_text, voice=chosen_voice, rate=rate, pitch=pitch)
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                yield chunk["data"]
    except Exception as e:
        logger.error(f"Error during TTS audio synthesis with voice '{chosen_voice}': {e}", exc_info=True)
