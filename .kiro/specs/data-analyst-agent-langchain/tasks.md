# Implementation Plan: Data Analyst Agent LangChain

## Overview

Replace the current chain-based text-to-SQL pipeline with a LangChain Agent architecture. The implementation follows an incremental approach: scaffold the agent package, extract and test core components (validator, formatter, memory), build the agent tools and service, then integrate with the existing API and Streamlit UI. Python is the implementation language, using LangChain with AWS Bedrock (Amazon Nova models).

## Tasks

- [ ] 1. Set up agent package scaffold and configuration
  - [ ] 1.1 Create agent package structure with __init__.py
    - Create `src/llm_sql/agent/__init__.py` with exports for AgentService and AgentResponse
    - Create empty module files for config, service, tools, validator, memory, models, formatter
    - _Requirements: 7.1, 7.2_

  - [ ] 1.2 Implement AgentSettings Pydantic configuration
    - Create `src/llm_sql/agent/config.py` with AgentSettings class extending BaseSettings
    - Define fields: AGENT_MAX_ITERATIONS (default 10), AGENT_MODEL, AGENT_TEMPERATURE (default 0.0), AGENT_MEMORY_MAX_TOKENS (default 4000), AGENT_MAX_RETRIES (default 3)
    - Add validation constraints (ge/le bounds) per design
    - _Requirements: 7.1, 7.2, 7.3_

  - [ ] 1.3 Integrate AgentSettings with existing Settings class
    - Compose AgentSettings into the existing `src/llm_sql/config.py` Settings class
    - Ensure env vars load correctly alongside existing configuration
    - _Requirements: 7.1, 7.2_

  - [ ] 1.4 Create response data models
    - Create `src/llm_sql/agent/models.py` with AgentResponse and AgentMetadata dataclasses
    - AgentResponse: answer (str), metadata (AgentMetadata | None)
    - AgentMetadata: sql_queries (list[str]), reasoning_steps (int), tools_used (list[str])
    - _Requirements: 8.2, 8.3, 11.3_

  - [ ]* 1.5 Write unit tests for AgentSettings validation
    - Test valid defaults load correctly
    - Test invalid values (out of bounds) raise SettingsError
    - Test env var override works
    - _Requirements: 7.2, 7.3_

- [ ] 2. Implement Query Validator
  - [ ] 2.1 Create QueryValidator class
    - Create `src/llm_sql/agent/validator.py` with QueryValidator class
    - Constructor accepts allowed_tables (set[str]) and max_result_rows (int)
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

  - [ ] 2.2 Implement validate method
    - Reject destructive keywords (DROP, DELETE, UPDATE, ALTER, INSERT, TRUNCATE, CREATE, REPLACE)
    - Reject queries not starting with SELECT or WITH
    - Reject multi-statement queries (semicolons followed by additional statements)
    - Reject queries referencing tables not in allowed set
    - Reject queries containing SQL comments (-- or /* */)
    - Return error message string if invalid, None if valid
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ] 2.3 Implement apply_limit method
    - Append LIMIT clause when missing using configured max_result_rows
    - Preserve existing LIMIT clause if already present
    - _Requirements: 4.6_

  - [ ]* 2.4 Write property test for destructive SQL rejection
    - **Property 1: Query Validator Rejects Destructive SQL**
    - Generate arbitrary SQL strings containing destructive keywords and verify validate() returns non-None
    - **Validates: Requirements 4.1, 4.2, 4.3, 4.5**

  - [ ]* 2.5 Write property test for apply_limit
    - **Property 2: Query Validator Preserves Valid SQL**
    - For valid SELECT queries without LIMIT, verify apply_limit output ends with LIMIT clause
    - **Validates: Requirements 4.6**

  - [ ] 2.6 Refactor core.py to use QueryValidator
    - Replace inline validation logic in `src/llm_sql/core.py` with QueryValidator calls
    - Maintain backward compatibility for existing chain-based flow
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6_

- [ ] 3. Checkpoint - Ensure validator tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 4. Implement Result Formatter
  - [ ] 4.1 Create formatter module
    - Create `src/llm_sql/agent/formatter.py` with format_results_as_table and format_agent_response functions
    - _Requirements: 11.1, 11.2_

  - [ ] 4.2 Implement markdown table formatting
    - Convert list of dicts to markdown table string with header row and data rows
    - Handle edge cases: empty results, single row, missing keys, long values
    - _Requirements: 11.2_

  - [ ] 4.3 Implement format_agent_response
    - Combine natural language answer text with formatted data tables
    - _Requirements: 11.1, 11.2_

  - [ ]* 4.4 Write property test for format_results_as_table
    - **Property 6: Result Formatter Round-Trip**
    - For any list of dicts with string keys and scalar values, verify output is valid markdown table
    - **Validates: Requirements 11.2**

- [ ] 5. Implement Conversation Memory Manager
  - [ ] 5.1 Create SessionMemoryManager class
    - Create `src/llm_sql/agent/memory.py` with SessionMemoryManager
    - Constructor accepts max_tokens (int)
    - _Requirements: 6.1, 6.3, 6.4_

  - [ ] 5.2 Implement get_memory and clear_session methods
    - get_memory(session_id) creates or retrieves ConversationTokenBufferMemory per session
    - clear_session(session_id) removes memory for a session
    - Enforce token limit by discarding oldest exchanges when exceeded
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

  - [ ]* 5.3 Write property test for memory token bound
    - **Property 5: Memory Token Bound**
    - For any sequence of exchanges, verify total token count never exceeds configured maximum
    - **Validates: Requirements 6.4**

  - [ ]* 5.4 Write unit test for session memory isolation
    - **Property 10: Session Memory Isolation**
    - Verify two distinct session IDs have independent memory that does not leak
    - **Validates: Requirements 6.3**

- [ ] 6. Implement Agent Tools
  - [ ] 6.1 Create tool factory module
    - Create `src/llm_sql/agent/tools.py` with tool factory functions
    - _Requirements: 2.1, 3.1, 10.1_

  - [ ] 6.2 Implement create_sql_tool
    - Create LangChain Tool that validates SQL via QueryValidator before execution
    - On validation failure, return error message without calling connector
    - On success, execute via connector.execute_sql and return formatted results
    - On database error, return error message for agent self-correction
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5_

  - [ ] 6.3 Implement create_schema_tool
    - Create LangChain Tool that returns full or filtered schema from connector
    - Include connector dialect in output for dialect-appropriate SQL generation
    - Support optional table name argument for filtered results
    - _Requirements: 3.1, 3.2, 3.3, 10.3_

  - [ ] 6.4 Implement create_validate_tool
    - Create LangChain Tool for dry-run SQL validation without execution
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

  - [ ]* 6.5 Write property test for SQL tool safety
    - **Property 3: SQL Tool Never Executes Invalid Queries**
    - For any SQL that QueryValidator rejects, verify connector.execute_sql is never called
    - **Validates: Requirements 2.1, 2.2**

  - [ ]* 6.6 Write unit tests for schema tool output
    - Verify output includes dialect string
    - Verify structured listing format with database, table, column names
    - **Validates: Requirements 3.1, 3.2, 10.3**

- [ ] 7. Checkpoint - Ensure all component tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 8. Implement Agent Service
  - [ ] 8.1 Create AgentService class
    - Create `src/llm_sql/agent/service.py` with AgentService class
    - Constructor accepts BaseConnector and AgentSettings
    - _Requirements: 1.1, 1.4, 10.1_

  - [ ] 8.2 Implement _build_executor method
    - Create LangChain AgentExecutor with ReAct agent using create_react_agent
    - Configure BedrockChat LLM with model settings from AgentSettings
    - Wire tools (sql_tool, schema_tool, validate_tool) and session memory
    - Set max_iterations, handle_parsing_errors=True, return_intermediate_steps=True
    - _Requirements: 1.1, 1.2, 1.4_

  - [ ] 8.3 Implement run_query method
    - Execute agent loop via AgentExecutor.invoke
    - Collect intermediate steps (SQL queries, reasoning)
    - Build and return AgentResponse with answer and metadata
    - Handle iteration limit exceeded with partial answer
    - _Requirements: 1.1, 1.2, 1.3, 1.5, 5.1, 5.2, 5.3_

  - [ ] 8.4 Implement retry logic
    - Track retry count per logical query (max 3 retries)
    - Include original error message in retry context for self-correction
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ]* 8.5 Write unit test for iteration limit
    - **Property 4: Agent Respects Iteration Limit**
    - Verify agent completes within configured max iterations using mock LLM
    - **Validates: Requirements 1.2**

  - [ ]* 8.6 Write unit test for AgentResponse contract
    - **Property 7: Agent Response Always Contains Answer**
    - Verify run_query always returns AgentResponse with non-empty answer field
    - **Validates: Requirements 8.2**

- [ ] 9. API Integration
  - [ ] 9.1 Extend API response model
    - Add optional `metadata` field to QueryResponse (sql_queries, reasoning_steps)
    - Maintain backward compatibility: "answer" field always present
    - _Requirements: 8.2, 8.3_

  - [ ] 9.2 Add agent mode routing
    - Add AGENT_MODE flag to settings (default True)
    - Modify `get_service()` in api.py to return AgentService when agent mode enabled
    - _Requirements: 8.1_

  - [ ] 9.3 Update query endpoint for agent responses
    - Update `/query` endpoint handler to process AgentResponse
    - Populate metadata field from AgentMetadata
    - Handle unrecoverable errors with HTTP 500 and descriptive message
    - _Requirements: 8.1, 8.2, 8.3, 8.4_

  - [ ] 9.4 Update health endpoint
    - Verify AgentService can be initialized without executing a query
    - _Requirements: 8.5_

  - [ ]* 9.5 Write unit tests for API backward compatibility
    - Verify response always contains "answer" field
    - Verify metadata is optional and present when available
    - _Requirements: 8.2, 8.3_

- [ ] 10. Streamlit UI Integration
  - [ ] 10.1 Add agent mode sidebar toggle
    - Add "🤖 Agent Mode" checkbox to sidebar (default on)
    - Maintain legacy chain mode when toggle is off
    - _Requirements: 9.4_

  - [ ] 10.2 Implement agent-mode query function
    - Create agent-mode `_ask` function calling AgentService.run_query with session_id
    - Display st.status progress indicator during agent processing
    - _Requirements: 9.3_

  - [ ] 10.3 Display reasoning steps and SQL queries
    - Show reasoning steps in `st.expander("🧠 Reasoning Steps")` below the answer
    - Display executed SQL queries in `st.code(sql, language="sql")` blocks
    - _Requirements: 9.1, 9.2_

  - [ ] 10.4 Wire connector switching to agent
    - Connect Streamlit data source selector to AgentService connector rebuilding
    - Rebuild agent tools when connector changes
    - _Requirements: 10.1, 10.2_

- [ ] 11. Checkpoint - Ensure integration tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 12. End-to-end testing and documentation
  - [ ]* 12.1 Write integration test for full agent loop
    - Test complete agent flow with mocked Bedrock and mocked connector
    - Verify question produces AgentResponse with SQL in metadata
    - _Requirements: 1.1, 1.5, 2.3_

  - [ ]* 12.2 Write integration test for self-correction flow
    - Simulate first query failure, verify agent retries with corrected SQL
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ]* 12.3 Write integration test for conversation memory
    - Send initial question then follow-up referencing prior context
    - Verify agent resolves references using memory
    - _Requirements: 6.1, 6.2_

  - [ ] 12.4 Update documentation and configuration
    - Update README.md with agent mode documentation and new environment variables
    - Add AGENT_* variables to `.env.template`
    - _Requirements: 7.1_

  - [ ] 12.5 Verify full test suite passes
    - Run `make test` and ensure all new and existing tests pass
    - _Requirements: all_

- [ ] 13. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation between major phases
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- Python 3.11 is the implementation language, matching the existing project stack
- LangChain with AWS Bedrock (Amazon Nova) is used for the agent LLM
- All existing safety guardrails (read-only, table allowlist, LIMIT enforcement) are preserved

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2", "1.4"] },
    { "id": 1, "tasks": ["1.3", "1.5", "2.1"] },
    { "id": 2, "tasks": ["2.2", "2.3", "4.1"] },
    { "id": 3, "tasks": ["2.4", "2.5", "2.6", "4.2", "5.1"] },
    { "id": 4, "tasks": ["4.3", "4.4", "5.2", "6.1"] },
    { "id": 5, "tasks": ["5.3", "5.4", "6.2", "6.3", "6.4"] },
    { "id": 6, "tasks": ["6.5", "6.6", "8.1"] },
    { "id": 7, "tasks": ["8.2", "8.3"] },
    { "id": 8, "tasks": ["8.4", "8.5", "8.6"] },
    { "id": 9, "tasks": ["9.1", "9.2", "10.1"] },
    { "id": 10, "tasks": ["9.3", "9.4", "10.2"] },
    { "id": 11, "tasks": ["9.5", "10.3", "10.4"] },
    { "id": 12, "tasks": ["12.1", "12.2", "12.3", "12.4"] },
    { "id": 13, "tasks": ["12.5"] }
  ]
}
```
