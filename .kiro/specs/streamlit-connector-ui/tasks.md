# Implementation Plan: Streamlit Connector UI

## Overview

This plan implements the enhanced sidebar connector management panel in incremental steps. We start with the pure helper module (`scripts/sidebar_helpers.py`) containing all testable logic, then build the UI components in `scripts/streamlit_app.py`, and finally wire everything together. Property-based tests validate correctness properties from the design, and unit tests cover specific examples and edge cases.

## Tasks

- [x] 1. Create sidebar helpers module with constants and pure functions
  - [x] 1.1 Create `scripts/sidebar_helpers.py` with type definitions, constants, and grouping logic
    - Define `CONNECTOR_ORDER`, `AWS_NATIVE_TYPES`, `EXTERNAL_TYPES`, `DIALECT_LABELS`, `CONNECTOR_ICONS`
    - Implement `group_connectors()` that partitions connector types into two groups preserving fixed display order
    - Implement `get_status_icon()` that checks config directory for enabled YAML files
    - Implement `resolve_active_selection()` that returns current selection or falls back to first item
    - Implement `get_connector_metadata()` returning dialect label and icon for a given type
    - _Requirements: 1.1, 1.3, 1.5, 5.1, 5.2_

  - [x] 1.2 Add template parsing, validation, and formatting functions to `scripts/sidebar_helpers.py`
    - Implement `extract_template_fields()` that parses `.yaml.template` files into field dicts with key and placeholder
    - Implement `validate_form_data()` that checks non-empty and max 255 chars, returning errors for invalid fields
    - Implement `build_yaml_config()` that constructs a config dict with `enabled: true` ready for YAML serialization
    - Implement `extract_status_panel_data()` that extracts type, host_or_account, database, status from a config dict
    - Implement `truncate_name()` that truncates to 50 chars with "..." suffix
    - Implement `format_test_success()` and `format_test_failure()` formatting functions
    - _Requirements: 2.1, 2.2, 3.1, 3.2, 3.3, 3.7, 4.4, 4.5, 5.3_

  - [x] 1.3 Write property tests for grouping, status icon, and selection fallback
    - **Property 1: Connector grouping preserves completeness and order**
    - **Property 2: Status icon reflects configuration state**
    - **Property 3: Selection fallback to first available**
    - **Validates: Requirements 1.1, 1.3, 1.5**
    - File: `tests/test_sidebar_properties.py`
    - Use `hypothesis` with `@settings(max_examples=100)`

  - [x] 1.4 Write property tests for template parsing, validation, and formatting
    - **Property 5: Template parsing produces matching form fields**
    - **Property 6: Configuration write/read round-trip**
    - **Property 7: Validation flags exactly the empty required fields**
    - **Property 9: Test failure preserves error message**
    - **Property 10: Test success contains dialect and valid ISO 8601 timestamp**
    - **Property 11: Connector metadata mapping is total and correct**
    - **Property 12: Name truncation respects length bounds**
    - **Validates: Requirements 2.2, 3.1, 3.2, 3.3, 3.7, 4.4, 4.5, 5.1, 5.2, 5.3**
    - File: `tests/test_sidebar_properties.py`

  - [x] 1.5 Write unit tests for sidebar helpers
    - Test `group_connectors` with all 6 types produces correct two groups
    - Test `get_status_icon` for athena (env-configured) and unconfigured types
    - Test `extract_template_fields` against real `redshift.yaml.template` and `snowflake.yaml.template`
    - Test `validate_form_data` boundary: empty, 255 chars valid, 256 chars invalid
    - Test `truncate_name` at exactly 50 and 51 characters
    - Test `extract_status_panel_data` for Athena vs External configs
    - Test `build_yaml_config` produces correct structure with `enabled: true`
    - File: `tests/test_sidebar_helpers.py`
    - _Requirements: 1.1, 1.3, 2.1, 3.1, 3.2, 3.3, 5.3_

- [x] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 3. Implement connector picker UI component
  - [x] 3.1 Implement `_render_connector_picker()` in `scripts/streamlit_app.py`
    - Render two group headers ("AWS Native", "External Platforms") that remain visible regardless of config state
    - Display each connector with emoji icon, name, and status icon (green check or orange warning)
    - Use `st.radio` or styled buttons for selection within each group
    - Persist selection to `st.session_state['active_connector_type']`
    - Handle fallback via `resolve_active_selection()` if previous selection is unavailable
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 5.1, 5.2, 5.4, 6.3_

  - [x] 3.2 Implement `_render_status_panel()` in `scripts/streamlit_app.py`
    - For configured External_Connector: display type, host/account, database, status indicator
    - For Athena: display Glue DB, region, workgroup from env/session state
    - For unconfigured: display setup prompt listing required fields from template
    - For unreadable config: display error indication with file path
    - For removed/disabled config: display "Configuration removed" warning with button to open config form
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 6.4_

- [x] 4. Implement inline configuration form
  - [x] 4.1 Implement `_render_config_form()` in `scripts/streamlit_app.py`
    - Load `.yaml.template` to determine field definitions; show error if template missing
    - Pre-populate from existing `.yaml` if present with `enabled: true`
    - Render `st.text_input` for each field (password type for secret/token/password keys)
    - Use template values as placeholder hints
    - On submit: validate via `validate_form_data()`, show per-field errors if invalid
    - On valid submit: write YAML via `build_yaml_config()` to `config/connections/`, update session state
    - Disable submit button if template unavailable
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7_

  - [x] 4.2 Write property tests for config pre-population and round-trip
    - **Property 4: Status panel extracts all required fields from config**
    - **Property 8: Config pre-population matches stored values**
    - **Validates: Requirements 2.1, 3.4**
    - File: `tests/test_sidebar_properties.py`

- [x] 5. Implement connection tester component
  - [x] 5.1 Implement `_render_connection_tester()` in `scripts/streamlit_app.py`
    - Only display "Test Connection" button when connector is configured
    - On click: show `st.spinner`, disable button, call `get_connector(name).test_connection()`
    - On success: display success badge with dialect + ISO 8601 timestamp via `format_test_success()`
    - On failure: display error badge with message via `format_test_failure()`
    - Cache test result in `st.session_state['test_result_{type}']`
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5_

- [x] 6. Implement unconfigured state banner and integrate into sidebar
  - [x] 6.1 Implement unconfigured query banner logic
    - When unconfigured connector is selected and user submits a query, show informational banner in sidebar
    - Banner states the connector type name and that it is not configured
    - Banner includes button/link to expand the Inline_Config_Form
    - Banner persists until user configures connector or selects a different type
    - Track banner state in `st.session_state['show_unconfigured_banner']` and `st.session_state['banner_connector_type']`
    - _Requirements: 6.1, 6.2, 6.3, 6.5_

  - [x] 6.2 Replace existing data source section in `_render_sidebar()` with new components
    - Remove the current flat selectbox data source picker code
    - Wire in `_render_connector_picker()`, `_render_status_panel()`, `_render_config_form()`, `_render_connection_tester()`
    - Maintain existing sections: logo, ALB URL, AWS Configuration expander, actions (Clear/Reconnect/Logout), footer
    - Ensure `st.session_state['active_source']` is updated from new `active_connector_type` for backward compatibility
    - _Requirements: 1.1, 1.2, 2.4, 2.5_

  - [x] 6.3 Write property test for unconfigured banner
    - **Property 13: Unconfigured connector query produces banner with connector type name**
    - **Validates: Requirements 6.1**
    - File: `tests/test_sidebar_properties.py`

- [x] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document
- Unit tests validate specific examples and edge cases
- All pure logic lives in `scripts/sidebar_helpers.py` for testability without Streamlit runtime
- UI components live in `scripts/streamlit_app.py` within the existing sidebar flow
- Run tests with: `PYTHONPATH=src python -m unittest discover -s tests -p "test_*.py" -v`
- Run property tests specifically: `PYTHONPATH=src python -m pytest tests/test_sidebar_properties.py -v`

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1"] },
    { "id": 1, "tasks": ["1.2"] },
    { "id": 2, "tasks": ["1.3", "1.4", "1.5"] },
    { "id": 3, "tasks": ["3.1", "3.2"] },
    { "id": 4, "tasks": ["4.1", "5.1"] },
    { "id": 5, "tasks": ["4.2", "6.1"] },
    { "id": 6, "tasks": ["6.2", "6.3"] }
  ]
}
```
