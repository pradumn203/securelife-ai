"""AI agents — every LLM-backed capability in the system.

Each agent is a class that owns one job, one prompt file under
`app/prompts/<agent_name>.md`, and one call shape against Groq:

    ChatAgent               streams the prospect-facing conversation
    ChatExtractorAgent      turns each chat turn into structured lead fields
    DocumentExtractorAgent  extracts policy data + evidence from a PDF's text
    AnalysisAgent           synthesises gaps / savings / risks for the broker

Shared infrastructure lives alongside them: `client` (process-wide Groq
client), `prompts` (markdown prompt loader), `errors` (user-safe error copy).
Agents never touch the database; routers and services own persistence.
"""
