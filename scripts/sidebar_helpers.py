"""Sidebar helper functions for the Streamlit connector management panel.

Contains pure functions and constants for connector grouping, status determination,
selection fallback, and metadata retrieval. Extracted for testability without
requiring a Streamlit runtime.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml


# Type definitions
ConnectorType = str  # e.g. "athena", "redshift", "rds_postgres"
ConnectorGroup = Literal["AWS Native", "External Platforms"]

# Constants - fixed display order for all connectors
CONNECTOR_ORDER: list[tuple[ConnectorType, str, str]] = [
    ("athena", "Athena", "☁️"),
    ("redshift", "Redshift", "🔴"),
    ("rds_postgres", "RDS PostgreSQL", "🐘"),
    ("rds_mysql", "RDS MySQL", "🐬"),
    ("snowflake", "Snowflake", "❄️"),
    ("databricks", "Databricks", "🧱"),
]

AWS_NATIVE_TYPES: set[ConnectorType] = {"athena", "redshift", "rds_postgres", "rds_mysql"}
EXTERNAL_TYPES: set[ConnectorType] = {"snowflake", "databricks"}

DIALECT_LABELS: dict[ConnectorType, str] = {
    "athena": "Athena SQL",
    "redshift": "Redshift SQL",
    "rds_postgres": "PostgreSQL",
    "rds_mysql": "MySQL",
    "snowflake": "Snowflake SQL",
    "databricks": "Spark SQL",
}

CONNECTOR_ICONS: dict[ConnectorType, str] = {
    "athena": "☁️",
    "redshift": "🔴",
    "rds_postgres": "🐘",
    "rds_mysql": "🐬",
    "snowflake": "❄️",
    "databricks": "🧱",
}

# Mapping from YAML file type values to our connector type keys
_YAML_TYPE_TO_KEY: dict[str, ConnectorType] = {
    "athena": "athena",
    "redshift": "redshift",
    "rds_postgres": "rds_postgres",
    "rds_mysql": "rds_mysql",
    "snowflake": "snowflake",
    "databricks": "databricks",
}

# Mapping from connector type keys to config/template file basenames
CONNECTOR_FILE_NAMES: dict[ConnectorType, str] = {
    "athena": "athena",
    "redshift": "redshift",
    "rds_postgres": "rds-postgres",
    "rds_mysql": "rds-mysql",
    "snowflake": "snowflake",
    "databricks": "databricks",
}


def get_config_filename(connector_type: ConnectorType) -> str:
    """Return the file basename for a connector type (without extension)."""
    return CONNECTOR_FILE_NAMES.get(connector_type, connector_type)


def group_connectors(
    connector_types: list[ConnectorType],
) -> dict[ConnectorGroup, list[ConnectorType]]:
    """Group connector types into AWS Native and External Platforms.

    Returns dict with two keys, each containing connectors in the fixed display
    order defined by CONNECTOR_ORDER. Only connectors present in the input list
    are included.
    """
    # Build ordered list for each group, preserving CONNECTOR_ORDER
    ordered_keys = [entry[0] for entry in CONNECTOR_ORDER]
    input_set = set(connector_types)

    aws_group: list[ConnectorType] = [
        ct for ct in ordered_keys if ct in input_set and ct in AWS_NATIVE_TYPES
    ]
    external_group: list[ConnectorType] = [
        ct for ct in ordered_keys if ct in input_set and ct in EXTERNAL_TYPES
    ]

    return {
        "AWS Native": aws_group,
        "External Platforms": external_group,
    }


def get_status_icon(connector_type: ConnectorType, config_dir: Path) -> str:
    """Return status icon for a connector type based on config directory state.

    Returns '✅' if a matching enabled YAML file exists in config_dir,
    '⚠️' otherwise.
    """
    if not config_dir.is_dir():
        return "⚠️"

    # Check all .yaml files in the config directory
    for yaml_file in config_dir.glob("*.yaml"):
        try:
            with open(yaml_file, "r") as f:
                config = yaml.safe_load(f)
            if not isinstance(config, dict):
                continue
            file_type = config.get("type", "")
            enabled = config.get("enabled", False)
            if file_type == connector_type and enabled is True:
                return "✅"
        except (yaml.YAMLError, OSError):
            continue

    return "⚠️"


def resolve_active_selection(
    current_selection: str | None,
    available_types: list[ConnectorType],
) -> ConnectorType:
    """Return current_selection if it's in available_types, else first item.

    If available_types is empty, returns empty string.
    """
    if not available_types:
        return ""
    if current_selection is not None and current_selection in available_types:
        return current_selection
    return available_types[0]


def get_connector_metadata(connector_type: ConnectorType) -> dict[str, str]:
    """Return dict with 'dialect_label' and 'icon' for the connector type.

    Returns default values if connector_type is unknown.
    """
    return {
        "dialect_label": DIALECT_LABELS.get(connector_type, "Unknown"),
        "icon": CONNECTOR_ICONS.get(connector_type, "❓"),
    }


def extract_template_fields(template_path: Path) -> list[dict[str, str]]:
    """Parse a .yaml.template file and return list of settings field dicts.

    Each dict has: {'key': field_name, 'placeholder': template_value}
    """
    with open(template_path, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        return []

    settings = data.get("settings")
    if not isinstance(settings, dict):
        return []

    return [
        {"key": key, "placeholder": str(value)}
        for key, value in settings.items()
    ]


def validate_form_data(
    fields: list[str],
    values: dict[str, str],
) -> dict[str, str]:
    """Validate form submission.

    Returns dict of field_name -> error_message for invalid fields.
    Empty dict means all valid. Checks: non-empty, max 255 chars.
    """
    errors: dict[str, str] = {}
    for field in fields:
        value = values.get(field, "")
        if not value or value.strip() == "":
            errors[field] = f"{field} is required"
        elif len(value) > 255:
            errors[field] = f"{field} must not exceed 255 characters"
    return errors


def build_yaml_config(
    connector_type: ConnectorType,
    name: str,
    settings: dict[str, str],
) -> dict:
    """Build a config dict ready for YAML serialization with enabled: true."""
    return {
        "name": name,
        "type": connector_type,
        "enabled": True,
        "settings": settings,
    }


def extract_status_panel_data(config: dict) -> dict[str, str]:
    """Extract display fields from a loaded connector config.

    Returns dict with keys: type, host_or_account, database, status.
    """
    connector_type = config.get("type", "unknown")
    settings = config.get("settings", {})
    if not isinstance(settings, dict):
        settings = {}

    # Prefer "host", fall back to "account"
    host_or_account = settings.get("host", settings.get("account", ""))

    database = settings.get("database", "")

    enabled = config.get("enabled", False)
    status = "Connected" if enabled else "Disconnected"

    return {
        "type": connector_type,
        "host_or_account": str(host_or_account),
        "database": str(database),
        "status": status,
    }


def truncate_name(name: str, max_length: int = 50) -> str:
    """Truncate name to max_length chars, adding '...' suffix if exceeded."""
    if len(name) > max_length:
        return name[:max_length] + "..."
    return name


def format_test_success(dialect: str, timestamp_iso: str) -> str:
    """Format a success badge string with dialect and ISO 8601 timestamp."""
    return f"✅ Connection successful ({dialect}) at {timestamp_iso}"


def format_test_failure(error_message: str) -> str:
    """Format a failure display string preserving the original error message."""
    return f"❌ Connection failed: {error_message}"


def get_connector_display_name(connector_type: ConnectorType) -> str:
    """Return the display name for a connector type from CONNECTOR_ORDER."""
    for type_key, display_name, _ in CONNECTOR_ORDER:
        if type_key == connector_type:
            return display_name
    return connector_type
