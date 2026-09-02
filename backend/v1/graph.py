from langgraph.graph import StateGraph, END
from backend.v1.agents.base import GraphState
from backend.v1.agents import (
    data_validator_node,
    categorizer_node,
    information_gatherer_node,
    contractor_categorizer_node,
    multi_task_architect_node,
    intake_node,
    tender_creator_node,
)

# --- Routing logic ---
def route(state: GraphState) -> str:
    return state.get("next_agent", "Categorizer")

def supervisor_node(state: GraphState) -> dict:
    next_agent = state.get("next_agent")
    if not next_agent or next_agent == "determine_number_of_subtasks" or next_agent == "Categorizer" and not state.get("CategorizerDecision"):
        # If it was Categorizer but we haven't done DataValidator yet, maybe we should start at DataValidator
        return {"next_agent": "DataValidator"}
    return {"next_agent": next_agent}

# --- Build Graph ---
workflow = StateGraph(GraphState)
workflow.add_node("Supervisor", supervisor_node)
workflow.add_node("DataValidator", data_validator_node)
workflow.add_node("Categorizer", categorizer_node)
workflow.add_node("InformationGatherer", information_gatherer_node)
workflow.add_node("ContractorCategorizer", contractor_categorizer_node)
workflow.add_node("MultiTaskArchitect", multi_task_architect_node)
workflow.add_node("IntakeCoordinator", intake_node)
workflow.add_node("TenderCreator", tender_creator_node)

def data_validator_edge(state: GraphState) -> str:
    next_agent = state.get("next_agent")
    if next_agent == "DataValidator":
        return END # Pause to wait for user reply (missing_context)
    return next_agent

def categorizer_edge(state: GraphState) -> str:
    return state.get("next_agent", "Categorizer")

def contractor_edge(state: GraphState) -> str:
    next_agent = state.get("next_agent")
    if next_agent == "ContractorCategorizer":
        return END # Pause to wait for user reply
    return next_agent

def architect_edge(state: GraphState) -> str:
    next_agent = state.get("next_agent")
    if next_agent == "MultiTaskArchitect":
        return END # Pause to wait for user reply
    return next_agent

def intake_edge(state: GraphState) -> str:
    next_agent = state.get("next_agent")
    if next_agent == "IntakeCoordinator":
        return END # Pause to wait for user reply
    return next_agent

workflow.set_entry_point("Supervisor")
workflow.add_conditional_edges(
    "Supervisor", 
    route,
    ["DataValidator", "Categorizer", "InformationGatherer", "ContractorCategorizer", "MultiTaskArchitect", "IntakeCoordinator", "TenderCreator"]
)

workflow.add_conditional_edges(
    "DataValidator",
    data_validator_edge,
    ["Categorizer", END]
)

workflow.add_conditional_edges(
    "Categorizer", 
    categorizer_edge,
    ["InformationGatherer", "ContractorCategorizer", "MultiTaskArchitect", "Categorizer"]
)
workflow.add_edge("InformationGatherer", END)
workflow.add_conditional_edges(
    "ContractorCategorizer", 
    contractor_edge,
    ["IntakeCoordinator", END]
)
workflow.add_conditional_edges(
    "MultiTaskArchitect", 
    architect_edge,
    ["IntakeCoordinator", END]
)
workflow.add_conditional_edges(
    "IntakeCoordinator", 
    intake_edge,
    ["TenderCreator", END]
)
workflow.add_edge("TenderCreator", END)

app = workflow.compile()
