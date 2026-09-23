import re
import json
from backend.llm import get_llm
from backend.v1.agents.base import GraphState
from backend.db import create_project
from backend.db.prompts_repository import get_similar_prompts_comments
from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import create_react_agent as create_agent

# Try to import sentence-transformers, fail gracefully if not ready yet
try:
    from sentence_transformers import SentenceTransformer
    embedder = SentenceTransformer('all-MiniLM-L6-v2')
except ImportError:
    embedder = None

def intake_node(state: GraphState) -> dict:
    """Collects and confirms client contact details, then saves the project.

    Uses any client details already present in `state["client_info"]` to
    avoid re-asking for information the system already has, confirms a
    pre-loaded address rather than silently trusting it, and once name,
    phone, and address are settled, saves the client and project via the
    `save_client_and_project` tool.

    Args:
        state: The current graph state. Reads `state["messages"]`,
            `state["client_info"]`, `state["user_id"]`, and
            `state["project_id"]`.

    Returns:
        A dict with updated `messages` and `project_id`. `next_agent` is set
        to "TenderCreator" once the project has been saved, or loops back to
        "IntakeCoordinator" if information is still being collected or
        confirmed.

    Note:
        No evaluator is wired for this node yet. If one is added
        (eval/intake_judge.py), its SYSTEM_PROMPT must be kept in sync
        with any future change to this node's collection/confirmation
        logic.
    """

    llm = get_llm()
    new_open_topics = state.get("open_topics", [])
    new_has_fetched = state.get("has_fetched_past_feedback", False)
    
    def _fetch_past_feedback(draft_markdown: str) -> str:
        """
        Generates a vector embedding for the draft document and searches past tenders
        for contractor feedback (comments) to ensure no critical info is missing.
        """
        nonlocal new_open_topics, new_has_fetched
        # TODO: this desigion might change in the future
        if new_has_fetched:
            return f"Already fetched. The current open topics are: {new_open_topics}"
            
        try:
            if not embedder:
                return "Embedder not loaded yet."
            
            # Generate embedding
            embedding = embedder.encode(draft_markdown).tolist()
            
            # Determine category
            cat_id = 1
            if state.get("identified_categories") and len(state.get("identified_categories")) > 0:
                cat_id = state.get("identified_categories")[0].get("category_id", cat_id)
            
            raw_comments = get_similar_prompts_comments(cat_id, embedding, limit=5)
            new_has_fetched = True
            
            parsed_comments = []
            if raw_comments:
                for rc in raw_comments:
                    try:
                        c_list = json.loads(rc)
                        if isinstance(c_list, list):
                            for c_item in c_list:
                                if isinstance(c_item, dict) and "comment" in c_item:
                                    parsed_comments.append(c_item["comment"])
                        else:
                            parsed_comments.append(rc)
                    except Exception:
                        parsed_comments.append(rc)

            if parsed_comments:
                return (
                    "PAST FEEDBACK FROM SIMILAR PROJECTS: " + " | ".join(parsed_comments) + "\n\n"
                    "INSTRUCTION: Review these comments. Check if they are relevant to this specific project, "
                    "AND check if the user has ALREADY provided this information. "
                    "If there is any relevant information still missing, you MUST call `update_open_topics` "
                    "to add those specific topics to the open topics list. If all are irrelevant or already answered, "
                    "you MUST still call `update_open_topics` with an empty list to confirm."
                )
            return "No relevant past feedback found."
        except Exception as e:
            return f"Error fetching feedback: {e}"

    def _update_open_topics(remaining_topics: list[str]) -> str:
        """
        Call this tool to update the list of open topics after the user answers a question, or after parsing past feedback.
        """
        nonlocal new_open_topics
        new_open_topics = remaining_topics
        if not new_open_topics:
            return "All topics resolved. You may now present the final draft for confirmation."
        return f"Updated open topics. Remaining: {new_open_topics}"

    def _confirm_and_save_document(document_markdown: str) -> str:
        """
        Saves the final confirmed document text. The user MUST explicitly say 'Yes' to this document before you call this tool.
        """
        try:
            client_id = state.get("user_id", 1)
            # Create a simple project record just to have a project ID. The TenderCreator will save the actual prompts.
            project_id = create_project(client_id=client_id, description="Drafting structured document...", comments="")
            
            # We return a specific token to signal success and pass the document text
            return f"SAVED_PROJECT_{project_id}_WITH_DOC:\n{document_markdown}"
        except Exception as e:
            return f"Failed to save to database: {e}"

    def _reject_document(reason: str) -> str:
        """
        Use this tool if the user says 'No' or rejects the document, routing them back to fix the details.
        """
        return "REJECTED_DOCUMENT"

    feedback_tool = StructuredTool.from_function(
        func=_fetch_past_feedback,
        name="fetch_past_feedback",
        description="Generates an embedding for the drafted job description and checks for past contractor feedback."
    )
    
    save_tool = StructuredTool.from_function(
        func=_confirm_and_save_document,
        name="confirm_and_save_document",
        description="Saves the final document AFTER the user explicitly confirms it."
    )
    
    reject_tool = StructuredTool.from_function(
        func=_reject_document,
        name="reject_document",
        description="Rejects the document and routes the user back to the previous data collection step."
    )
    
    update_topics_tool = StructuredTool.from_function(
        func=_update_open_topics,
        name="update_open_topics",
        description="Call this tool to update the list of open topics after the user answers a question."
    )
    
    client_info_str = f"{state.get('client_info', {})}"
    topics_str = f"{new_open_topics}" if new_open_topics else "None"
    has_fetched_str = "YES" if new_has_fetched else "NO"
    system_prompt = (
        "You are the Intake Coordinator.\n"
        f"CRITICAL INSTRUCTION: You have these client details pre-loaded: {client_info_str}\n"
        f"PAST FEEDBACK FETCHED YET: {has_fetched_str}\n"
        f"CURRENT OPEN TOPICS (must be resolved): {topics_str}\n\n"
        "Your PRIMARY GOAL depends on the current state:\n"
        "1. IF 'PAST FEEDBACK FETCHED YET' is NO:\n"
        "   - You MUST immediately call the `fetch_past_feedback` tool with a draft of the job description.\n"
        "   - DO NOT show the draft to the user yet. Just call the tool.\n\n"
        "2. IF 'PAST FEEDBACK FETCHED YET' is YES AND 'CURRENT OPEN TOPICS' is NOT 'None' AND 'CURRENT OPEN TOPICS' is NOT '[]':\n"
        "   - Your ONLY job is to ask the user the questions required to resolve those topics.\n"
        "   - DO NOT output the Markdown draft at all. Just ask the questions.\n"
        "   - As the user answers questions, call `update_open_topics` to remove them.\n\n"
        "3. IF 'PAST FEEDBACK FETCHED YET' is YES AND ('CURRENT OPEN TOPICS' is 'None' OR 'CURRENT OPEN TOPICS' is '[]') (all topics resolved):\n"
        "   - Output the structured job description in the EXACT Markdown format below, and ask the user to confirm it.\n"
        "\n"
        "MARKDOWN FORMAT TO USE (ONLY for step 3):\n"
        "**[Major Category Name]**\n\n"
        "**Description:**\n"
        "[General Description including any details gathered]\n\n"
        "**Address:**\n"
        "[Address]\n\n"
        "---\n\n"
        "ADDITIONAL RULES:\n"
        "- If the user confirms the markdown document (e.g., 'Yes', 'Looks good'), you MUST IMMEDIATELY call `confirm_and_save_document` passing the EXACT markdown document. Then output ALL_DONE.\n"
        "- If the user says 'No' or wants to edit, you MUST call `reject_document`."
    )
    
    agent = create_agent(model=llm, tools=[feedback_tool, save_tool, reject_tool, update_topics_tool], prompt=system_prompt)
    
    try:
        result = agent.invoke({"messages": state["messages"]})
        last_message = result["messages"][-1]
        content_str = last_message.content if hasattr(last_message, 'content') else last_message.get("content", "")
        
        project_id = state.get("project_id")
        next_agent = "IntakeCoordinator"
        confirmed_job_description = state.get("confirmed_job_description")
        
        # Check tool outputs from the result messages
        for msg in reversed(result["messages"]):
            if getattr(msg, "type", "") == "tool":
                if "SAVED_PROJECT_" in str(msg.content):
                    match = re.search(r'SAVED_PROJECT_(\d+)_WITH_DOC:\n(.*)', str(msg.content), re.DOTALL)
                    if match:
                        project_id = int(match.group(1))
                        confirmed_job_description = match.group(2).strip()
                        next_agent = "TenderCreator"
                        
                        clean_content = re.sub(r'ALL_DONE', '', content_str).strip()
                        if not clean_content:
                            clean_content = "Perfect! Your document is confirmed. I'm preparing the final tenders for the contractors now."
                        
                        if hasattr(last_message, 'content'):
                            result["messages"][-1] = AIMessage(content=clean_content)
                        else:
                            result["messages"][-1]["content"] = clean_content
                    break
                elif "REJECTED_DOCUMENT" in str(msg.content):
                    # Route back to previous collection node
                    if state.get("CategorizerDecision") and getattr(state.get("CategorizerDecision"), "has_subtasks", False):
                        next_agent = "MultiTaskArchitect"
                    else:
                        next_agent = "ContractorCategorizer"
                        
                    clean_content = "I've routed you back so you can fix the details. What needs to change?"
                    if hasattr(last_message, 'content'):
                        result["messages"][-1] = AIMessage(content=clean_content)
                    else:
                        result["messages"][-1]["content"] = clean_content
                    break
            
        return {
            "messages": result["messages"],
            "next_agent": next_agent,
            "project_id": project_id,
            "confirmed_job_description": confirmed_job_description,
            "open_topics": new_open_topics,
            "has_fetched_past_feedback": new_has_fetched
        }
    except Exception as e:
        return {"messages": state["messages"] + [{"role": "assistant", "content": f"Intake error: {e}"}]}
