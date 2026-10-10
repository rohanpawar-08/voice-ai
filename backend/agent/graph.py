import json
import logging
import os
import time
from typing import Annotated, Any, Callable, Dict, List, Optional, TypedDict
from langchain_core.messages import BaseMessage, SystemMessage, HumanMessage, AIMessage, ToolMessage
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, START, END
from langgraph.graph.message import add_messages

from config import settings
from agent.tools import AVAILABLE_TOOLS, TOOL_MAP

logger = logging.getLogger("copilot.agent")

SYSTEM_PROMPT = (
    "You are Sarah, the warm, professional, and fluent bilingual (Marathi and English) AI Voice Receptionist for "
    "'साई स्माईल डेंटल क्लिनिक व इम्प्लांट सेंटर (Sai Smile Dental Clinic & Implant Centre)' "
    "located at शिवाजी नगर, पुणे / सातारा, महाराष्ट्र (Shivaji Nagar, Pune / Satara, Maharashtra) "
    "(Clinic hours: Mon-Sat 9:00 AM - 8:30 PM, Sun 10:00 AM - 2:00 PM).\n\n"
    "Pricing & Currency Rule (MANDATORY):\n"
    "- ALWAYS quote prices in Indian Rupees (₹ / रुपये) and explicitly speak prices as 'रुपये' (Rupees). NEVER mention dollars ($).\n"
    "- Standard Clinic Treatments & Doctors:\n"
    "  * Dental Cleaning & Hygiene (दात स्वच्छ करणे / क्लिनिंग): ₹800 (८०० रुपये) - डॉ. स्नेहा पाटील (30 min)\n"
    "  * Root Canal Therapy (रूट कॅनल ट्रीटमेंट): ₹3,500 (३,५०० रुपये) - डॉ. राहुल देशमुख (60 min)\n"
    "  * Teeth Whitening (दात पांढरे करणे / व्हाईटनिंग): ₹2,500 (२,५०० रुपये) - डॉ. स्नेहा पाटील (45 min)\n"
    "  * Consultation & Checkup (सामान्य तपासणी): ₹300 (३०० रुपये) - डॉ. अमित जोशी (20 min)\n"
    "  * Tooth Extraction (दात काढणे): ₹1,000 (१,००० रुपये) - डॉ. राहुल देशमुख (30 min)\n"
    "  * Clear Aligners (इनव्हिसिलाइन सल्ला): मोफत (Free ₹0 Consultation) - डॉ. अमित जोशी\n\n"
    "Language & Spoken Guidelines:\n"
    "- If the caller speaks in Marathi, respond naturally in polite, conversational Marathi using clean Devanagari script.\n"
    "- If the caller speaks in English, respond in clear English.\n"
    "- If the caller mixes Marathi and English (code-switching), understand seamlessly and respond in warm, natural Marathi.\n"
    "- Keep spoken responses concise, warm, and friendly (1 to 3 spoken sentences max).\n\n"
    "Tool Execution & Clinic Booking Guidelines:\n"
    "1. Extract patient details, dates, times, and service requests accurately from Marathi or English queries to trigger tools.\n"
    "2. When callers ask about procedures, treatments, pricing, or doctors (e.g. cleaning / दात क्लिनिंग / तपासणी, root canal / रूट कॅनल, whitening / दात पांढरे करणे, checkup, extraction / दात काढणे, invisalign), invoke check_service_info.\n"
    "3. When callers inquire about open slots or available consultation times (e.g. उद्या / tomorrow, सोमवार / Monday, etc.), invoke check_available_slots.\n"
    "4. When booking an appointment, gather their name, phone, preferred date, time slot, and treatment, then invoke book_appointment to confirm and save their appointment.\n"
    "5. For greetings (e.g. 'नमस्कार', 'Hello', 'Good morning') or general queries, reply warmly as Sarah from Sai Smile Dental Clinic and offer to help schedule their dental visit."
)


class CopilotState(TypedDict):
    messages: Annotated[List[BaseMessage], add_messages]
    session_id: str
    allowed_tools: Optional[List[str]]


def get_llm():
    api_key = settings.GROQ_API_KEY or os.getenv("GROQ_API_KEY")
    if not api_key:
        return None
    return ChatGroq(
        model=settings.LLM_MODEL,
        groq_api_key=api_key,
        temperature=0.2,
        max_retries=2,
    )


# Build the LangGraph StateGraph
def build_copilot_graph():
    builder = StateGraph(CopilotState)

    async def agent_node(state: CopilotState):
        messages = list(state.get("messages", []))
        if not messages or not isinstance(messages[0], SystemMessage):
            messages = [SystemMessage(content=SYSTEM_PROMPT)] + messages

        llm = get_llm()
        if llm is None:
            return {
                "messages": [
                    AIMessage(
                        content="साई स्माईल डेंटल क्लिनिकमध्ये आपले स्वागत आहे! (Welcome to Sai Smile Dental Clinic!) How may I help you with your dental health today?"
                    )
                ]
            }

        try:
            llm_with_tools = llm.bind_tools(AVAILABLE_TOOLS)
            response = await llm_with_tools.ainvoke(messages)
            return {"messages": [response]}
        except Exception as e:
            logger.error(f"Error in agent_node LLM invocation: {e}", exc_info=True)
            try:
                response = await llm.ainvoke(messages)
                return {"messages": [response]}
            except Exception as e2:
                logger.error(f"Fallback direct LLM invocation failed: {e2}")
                return {
                    "messages": [
                        AIMessage(content="नमस्कार, साई स्माईल डेंटल क्लिनिकमध्ये आपले स्वागत आहे! मी सारा, आपली कशी मदत करू? (Welcome to Sai Smile Dental Clinic! How may I assist you?)")
                    ]
                }

    async def tool_node(state: CopilotState):
        if not state or "messages" not in state or not state["messages"]:
            return {"messages": []}

        last_message = state["messages"][-1]
        tool_messages = []
        tool_calls = getattr(last_message, "tool_calls", None) or []
        allowed = set(state.get("allowed_tools") or [])

        for tc in tool_calls:
            tool_name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", None)
            tool_args = tc.get("args", {}) if isinstance(tc, dict) else getattr(tc, "args", {})
            tool_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", f"call_{int(time.time() * 1000)}")

            if allowed and tool_name not in allowed:
                logger.warning(f"Tool execution blocked for unauthorized tool '{tool_name}' in session {state.get('session_id')}")
                res = json.dumps({"error": f"Access denied: Tool '{tool_name}' is not authorized for this session."})
            else:
                tool_fn = TOOL_MAP.get(tool_name)
                if tool_fn:
                    try:
                        res = tool_fn.invoke(tool_args)
                    except Exception as e:
                        logger.error(f"Tool execution failed for '{tool_name}': {e}")
                        res = json.dumps({"error": f"Tool execution failed: {str(e)}"})
                else:
                    res = json.dumps({"error": f"Tool '{tool_name}' not found."})

            tool_messages.append(
                ToolMessage(
                    content=str(res),
                    tool_call_id=tool_id,
                    name=tool_name or "unknown_tool"
                )
            )
        return {"messages": tool_messages}

    def should_continue(state: CopilotState) -> str:
        if not state or "messages" not in state or not state["messages"]:
            return END
        last_message = state["messages"][-1]
        tool_calls = getattr(last_message, "tool_calls", None)
        if tool_calls and len(tool_calls) > 0:
            return "tools"
        return END

    builder.add_node("agent", agent_node)
    builder.add_node("tools", tool_node)

    builder.add_edge(START, "agent")
    builder.add_conditional_edges("agent", should_continue, ["tools", END])
    builder.add_edge("tools", "agent")

    return builder.compile()


copilot_graph = build_copilot_graph()


async def execute_agent_workflow(
    messages: List[BaseMessage],
    session_id: str,
    emit_event: Optional[Callable[[Dict[str, Any]], Any]] = None,
    allowed_tools: Optional[List[str]] = None
) -> tuple[str, List[Dict[str, Any]]]:
    """
    Executes the LangGraph multi-turn agent workflow for VoiceDesk AI clinic receptionist.
    Handles service info, live slot availability, appointment confirmations, and general queries.
    """
    start_time = time.perf_counter()
    tools_executed: List[Dict[str, Any]] = []

    if emit_event:
        await emit_event({"type": "agent_thinking", "session_id": session_id})

    llm = get_llm()
    if llm is None:
        demo_text = (
            "Hello! Thank you for calling Apex Dental & Wellness Care. "
            "Configure your free GROQ_API_KEY in backend/.env to activate live AI voice bookings."
        )
        if emit_event:
            await emit_event({
                "type": "agent_response",
                "text": demo_text,
                "latency_ms": 10,
                "tools_used": [],
                "session_id": session_id
            })
        return demo_text, []

    current_state = {
        "messages": messages,
        "session_id": session_id,
        "allowed_tools": allowed_tools
    }
    final_text = ""

    try:
        async for output in copilot_graph.astream(current_state, stream_mode="updates"):
            for node_name, node_update in output.items():
                if node_name == "agent":
                    agent_msgs = node_update.get("messages", [])
                    if agent_msgs:
                        agent_msg = agent_msgs[-1]
                        tool_calls = getattr(agent_msg, "tool_calls", None) or []
                        if tool_calls:
                            for tc in tool_calls:
                                name = tc.get("name") if isinstance(tc, dict) else getattr(tc, "name", "")
                                args = tc.get("args") if isinstance(tc, dict) else getattr(tc, "args", {})
                                call_id = tc.get("id") if isinstance(tc, dict) else getattr(tc, "id", "")
                                logger.info(f"Sarah (AI Receptionist) calling tool: {name} with args {args}")
                                if emit_event:
                                    await emit_event({
                                        "type": "tool_call_start",
                                        "tool": name,
                                        "args": args,
                                        "call_id": call_id,
                                        "session_id": session_id,
                                        "timestamp": time.time()
                                    })
                        else:
                            content = getattr(agent_msg, "content", "")
                            if isinstance(content, list):
                                text_parts = [b.get("text", "") if isinstance(b, dict) else str(b) for b in content]
                                final_text = "".join(text_parts).strip()
                            else:
                                final_text = str(content or "").strip()

                elif node_name == "tools":
                    for t_msg in node_update.get("messages", []):
                        raw_output = t_msg.content
                        try:
                            parsed_output = json.loads(raw_output)
                        except Exception:
                            parsed_output = raw_output

                        tools_executed.append({
                            "tool": t_msg.name,
                            "call_id": t_msg.tool_call_id,
                            "output": parsed_output
                        })

                        logger.info(f"Clinic tool executed: {t_msg.name}")
                        if emit_event:
                            await emit_event({
                                "type": "tool_call_result",
                                "tool": t_msg.name,
                                "call_id": t_msg.tool_call_id,
                                "output": parsed_output,
                                "session_id": session_id,
                                "timestamp": time.time()
                            })

    except Exception as e:
        logger.error(f"LangGraph execution error: {e}", exc_info=True)
        final_text = f"Thank you for contacting Apex Dental. I can assist you with your booking. Could you please repeat that?"

    if not final_text:
        final_text = "Welcome to Apex Dental & Wellness Care! How can I help you today?"

    total_latency_ms = round((time.perf_counter() - start_time) * 1000)

    if emit_event:
        await emit_event({
            "type": "agent_response",
            "text": final_text,
            "latency_ms": total_latency_ms,
            "tools_used": tools_executed,
            "session_id": session_id,
            "timestamp": time.time()
        })

    return final_text, tools_executed
