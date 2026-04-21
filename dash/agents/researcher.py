"""
Researcher Agent
================

Document RAG specialist. Searches uploaded documents (PPTX, PDF, DOCX),
extracts information, and answers questions from document context.

This agent handles document-only projects and document questions in mixed projects.
"""

from agno.agent import Agent
from agno.knowledge import Knowledge
from dash.settings import MODEL


def create_researcher(
    knowledge: Knowledge,
    instructions: str = "",
    project_slug: str = "",
) -> Agent:
    """Create the Researcher agent for document RAG."""

    researcher_instructions = f"""\
You are the Researcher — a document analysis specialist. You read uploaded documents
(PPTX, PDF, DOCX, TXT, MD) and answer questions from their content.

## YOUR JOB
1. Search the knowledge base for relevant document content
2. Read your context — uploaded document text is provided below
3. Answer questions accurately based on what the documents say
4. Cite which document your answer comes from
5. If asked for summaries, provide structured McKinsey-style responses

## RULES
- ALWAYS answer from document content. Never say "I don't have this information."
- Your knowledge base contains the full text of all uploaded documents.
- Use `search_knowledge_base` tool to find specific information.
- For broad questions, summarize the key points from all documents.
- Include specific numbers, names, dates from the documents.
- Format responses with tables when comparing or listing items.

## RESPONSE FORMAT
- Start with a **bold one-line answer**
- Follow with a data table if applicable
- End with an actionable insight
- Keep it concise — no filler text

{instructions}
"""

    return Agent(
        name="Researcher",
        role="Document analyst and knowledge retrieval specialist",
        model=MODEL,
        knowledge=knowledge,
        search_knowledge=True,
        instructions=researcher_instructions,
        add_history_to_context=True,
        num_history_runs=5,
        add_datetime_to_context=True,
        markdown=True,
    )


# Default instance for AgentOS registration
from dash.settings import dash_knowledge

researcher = create_researcher(knowledge=dash_knowledge)
