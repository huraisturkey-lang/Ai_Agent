# Requirements Document

## Introduction

This feature improves the Streamlit chat UI treatment for non-Athena data source connectors (Redshift, RDS PostgreSQL, RDS MySQL, Snowflake, Databricks). The current UI shows a flat selectbox with minimal status indicators and returns plain-text error messages when connectors are unconfigured. The improved UI provides visual connector grouping, rich connection status panels, an inline configuration form for quick setup, and connection testing - all within the sidebar - so users can discover, configure, and manage multiple data sources without leaving the application.

## Glossary

- **Sidebar**: The left-side panel in the Streamlit chat UI containing navigation, settings, and data source selection
- **Connector_Picker**: The UI component that displays available data source connectors grouped by category and shows their configuration status
- **Connection_Status_Panel**: A visual indicator component displaying the health, configuration state, and key metadata of a selected connector
- **Inline_Config_Form**: An expandable form within the sidebar that allows users to enter connector settings (host, port, database, credentials) without editing YAML files manually
- **Connection_Tester**: A UI component that validates connectivity to a configured data source and displays results
- **Connector_Card**: A styled UI element representing a single data source option with icon, name, type badge, and status indicator
- **Config_Registry**: The existing YAML-based configuration system in `config/connections/` that stores data source connection details
- **Athena_Connector**: The default AWS Athena data source configured via environment variables
- **External_Connector**: Any non-Athena data source (Redshift, RDS PostgreSQL, RDS MySQL, Snowflake, Databricks) configured via YAML files

## Requirements

### Requirement 1: Grouped Connector Display

**User Story:** As a data analyst, I want to see connectors organized by category, so that I can quickly locate the data source type I need.

#### Acceptance Criteria

1. THE Connector_Picker SHALL display connectors in two groups: "AWS Native" (Athena, Redshift, RDS PostgreSQL, RDS MySQL) and "External Platforms" (Snowflake, Databricks), with connectors listed in that fixed order within each group
2. WHEN the Sidebar renders the data source section, THE Connector_Picker SHALL display each group with a visible header label, and both group headers SHALL remain visible even when all connectors within a group are unconfigured
3. THE Connector_Picker SHALL display a status icon next to each connector name: a green checkmark for configured connectors and an orange warning icon for unconfigured connectors, where a connector is considered "configured" when a corresponding enabled YAML file exists in the connections configuration directory and "unconfigured" otherwise
4. THE Connector_Picker SHALL preserve the currently active source selection in session state across Streamlit rerenders within the same browser session
5. IF the previously active source selection is no longer available when the Connector_Picker renders, THEN THE Connector_Picker SHALL fall back to the first connector in the list as the active selection

### Requirement 2: Connection Status Panel

**User Story:** As a data analyst, I want to see detailed connection information for my selected data source, so that I can verify it is properly configured before querying.

#### Acceptance Criteria

1. WHEN a configured External_Connector is selected, THE Connection_Status_Panel SHALL display the connector type, host or account identifier, database name, and a status indicator showing one of: "Connected", "Configuration Error", or "Unreachable"
2. WHEN an unconfigured External_Connector is selected, THE Connection_Status_Panel SHALL display a setup prompt listing the required configuration fields as defined in that connector type's YAML template
3. WHILE the Athena_Connector is selected, THE Connection_Status_Panel SHALL display the Glue database name, AWS region, and Athena workgroup read from the current environment or YAML configuration
4. THE Connection_Status_Panel SHALL render within the Sidebar below the Connector_Picker
5. WHEN the user selects a different connector in the Connector_Picker, THE Connection_Status_Panel SHALL update its displayed information to reflect the newly selected connector within 1 second
6. IF the Connection_Status_Panel cannot read the configuration for the selected connector, THEN THE Connection_Status_Panel SHALL display an error indication stating that the configuration file is missing or unreadable

### Requirement 3: Inline Configuration Form

**User Story:** As a developer, I want to configure data source connections directly in the UI, so that I can set up new connectors without manually editing YAML files.

#### Acceptance Criteria

1. WHEN an External_Connector is selected that has no corresponding `.yaml` file in `config/connections/` or whose file has `enabled: false`, THE Inline_Config_Form SHALL display input fields matching the required settings defined in that connector type's `.yaml.template` file
2. WHEN the user submits the Inline_Config_Form and all required fields contain non-empty values with each field value not exceeding 255 characters, THE Config_Registry SHALL write a new YAML configuration file to `config/connections/` with the provided settings and `enabled: true`
3. IF the user submits the Inline_Config_Form with one or more required fields empty, THEN THE Inline_Config_Form SHALL display a validation error message adjacent to each empty required field identifying it as required
4. IF a `.yaml` configuration file already exists for the selected connector with `enabled: true`, THEN THE Inline_Config_Form SHALL pre-populate fields with the existing values and allow the user to update them
5. WHEN the Inline_Config_Form successfully saves a configuration, THE Connection_Status_Panel SHALL update the connector status from unconfigured to configured within 2 seconds without requiring a page reload
6. IF the corresponding `.yaml.template` file does not exist for the selected connector type, THEN THE Inline_Config_Form SHALL display an error message indicating the template is unavailable and disable the submit action
7. THE Inline_Config_Form SHALL pre-populate fields with values from the corresponding `.yaml.template` file as placeholder hints

### Requirement 4: Connection Testing

**User Story:** As a developer, I want to test my data source connection from the UI, so that I can verify connectivity before running queries.

#### Acceptance Criteria

1. WHEN a configured External_Connector is selected, THE Connection_Tester SHALL display a "Test Connection" button
2. WHEN the user clicks the "Test Connection" button, THE Connection_Tester SHALL invoke the connector's `test_connection()` method and display a success or failure result
3. WHILE a connection test is in progress, THE Connection_Tester SHALL display a loading spinner and disable the "Test Connection" button to prevent duplicate requests
4. IF the connection test fails, THEN THE Connection_Tester SHALL display the error message returned by the connector
5. WHEN the connection test succeeds, THE Connection_Tester SHALL display a success badge with the connector dialect and a timestamp in ISO 8601 format

### Requirement 5: Connector Type Metadata Display

**User Story:** As a data analyst, I want to see useful metadata about each connector type, so that I can understand what each data source offers.

#### Acceptance Criteria

1. THE Connector_Card SHALL display a type badge indicating the SQL dialect using the following labels: "Athena SQL" for Athena, "PostgreSQL" for RDS PostgreSQL, "MySQL" for RDS MySQL, "Redshift SQL" for Redshift, "Snowflake SQL" for Snowflake, and "Spark SQL" for Databricks
2. THE Connector_Card SHALL display the connector icon matching its type (existing emoji icons: cloud for Athena, red circle for Redshift, elephant for PostgreSQL, dolphin for MySQL, snowflake for Snowflake, brick for Databricks)
3. WHEN a configured connector is selected, THE Connector_Card SHALL display the connection name from the YAML configuration, truncated to 50 characters with an ellipsis suffix if the name exceeds that length
4. IF a connector type has no YAML configuration file present, THEN THE Connector_Card SHALL display the type badge and icon but omit the connection name and show a status indicator that the connector is not configured

### Requirement 6: Graceful Unconfigured State

**User Story:** As a new user, I want clear guidance when a connector is not configured, so that I can set it up correctly on my first attempt.

#### Acceptance Criteria

1. WHEN an unconfigured External_Connector is selected and the user submits a query, THE Sidebar SHALL display an informational banner that states the selected connector is not configured and names the connector type, instead of returning an error in the chat
2. WHEN the informational banner is displayed, THE informational banner SHALL include a direct link or button that expands the Inline_Config_Form for the selected connector type
3. WHEN no External_Connectors are configured, THE Connector_Picker SHALL display all supported connector types as selectable options, each showing a textual "Not configured" status indicator adjacent to the connector name
4. IF a previously configured connector becomes invalid (YAML file removed or `enabled: false`), THEN THE Connection_Status_Panel SHALL display a "Configuration removed" warning and a button that opens the Inline_Config_Form pre-populated with the connector type for reconfiguration
5. WHEN the informational banner is displayed, THE Sidebar SHALL continue to display the banner until the user either configures the connector or selects a different connector type
