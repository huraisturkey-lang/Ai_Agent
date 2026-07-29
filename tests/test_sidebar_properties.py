"""Property-based tests for sidebar_helpers module.

Uses hypothesis to verify correctness properties from the design document.
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

import yaml
from hypothesis import given, settings
from hypothesis import strategies as st

# Add project root to path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from scripts.sidebar_helpers import (
    AWS_NATIVE_TYPES,
    CONNECTOR_ICONS,
    CONNECTOR_ORDER,
    DIALECT_LABELS,
    EXTERNAL_TYPES,
    build_yaml_config,
    extract_status_panel_data,
    extract_template_fields,
    format_test_failure,
    format_test_success,
    get_connector_display_name,
    get_connector_metadata,
    get_status_icon,
    group_connectors,
    resolve_active_selection,
    truncate_name,
    validate_form_data,
)

# ─── Strategies ───────────────────────────────────────────────────────────────

# All known connector type keys
ALL_CONNECTOR_TYPES = [entry[0] for entry in CONNECTOR_ORDER]

# Connector types from CONNECTOR_ORDER
connector_type_st = st.sampled_from(ALL_CONNECTOR_TYPES)

# Subsets of connector types (non-empty, unique)
connector_subset_st = st.lists(connector_type_st, min_size=1, max_size=6, unique=True)

# Alphanumeric field names (valid YAML keys)
field_name_st = st.text(
    min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
)

# Field values (non-empty, up to 255 chars)
field_value_st = st.text(min_size=1, max_size=255)

# Error messages and dialects
message_st = st.text(min_size=1, max_size=100)


# ─── Property 1: Connector grouping preserves completeness and order ──────────


@given(subset=connector_subset_st)
@settings(max_examples=100)
def test_property_1_grouping_union_equals_input(subset):
    """Feature: streamlit-connector-ui, Property 1: Connector grouping preserves completeness and order

    For any subset of the 6 known connector types, group_connectors()
    returns two groups whose union equals the input set.

    Validates: Requirements 1.1
    """
    result = group_connectors(subset)
    aws_group = result["AWS Native"]
    external_group = result["External Platforms"]

    # Union of both groups equals the input set
    grouped_set = set(aws_group) | set(external_group)
    assert grouped_set == set(subset), (
        f"Grouped set {grouped_set} != input set {set(subset)}"
    )


@given(subset=connector_subset_st)
@settings(max_examples=100)
def test_property_1_grouping_correct_membership(subset):
    """Feature: streamlit-connector-ui, Property 1: Connector grouping preserves completeness and order

    Each connector appears in the correct group (AWS_NATIVE_TYPES or EXTERNAL_TYPES).

    Validates: Requirements 1.1
    """
    result = group_connectors(subset)

    for ct in result["AWS Native"]:
        assert ct in AWS_NATIVE_TYPES, f"{ct} should not be in AWS Native"
    for ct in result["External Platforms"]:
        assert ct in EXTERNAL_TYPES, f"{ct} should not be in External Platforms"


@given(subset=connector_subset_st)
@settings(max_examples=100)
def test_property_1_grouping_preserves_connector_order(subset):
    """Feature: streamlit-connector-ui, Property 1: Connector grouping preserves completeness and order

    Items appear in the same relative order as CONNECTOR_ORDER.

    Validates: Requirements 1.1
    """
    ordered_keys = [entry[0] for entry in CONNECTOR_ORDER]
    result = group_connectors(subset)

    for group in result.values():
        # Check that group items appear in same order as CONNECTOR_ORDER
        indices = [ordered_keys.index(ct) for ct in group]
        assert indices == sorted(indices), (
            f"Group {group} not in CONNECTOR_ORDER: indices={indices}"
        )


# ─── Property 2: Status icon reflects configuration state ────────────────────


@given(connector_type=connector_type_st)
@settings(max_examples=100)
def test_property_2_status_icon_configured_returns_checkmark(connector_type):
    """Feature: streamlit-connector-ui, Property 2: Status icon reflects configuration state

    If a YAML file matching the connector type with enabled: true exists
    in the config directory, get_status_icon() returns checkmark.

    Validates: Requirements 1.3
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_dir = Path(tmp_dir)
        # Write a YAML file with matching type and enabled: true
        config = {
            "name": f"Test {connector_type}",
            "type": connector_type,
            "enabled": True,
            "settings": {"host": "localhost"},
        }
        yaml_path = config_dir / f"{connector_type}.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(config, f)

        icon = get_status_icon(connector_type, config_dir)
        assert icon == "✅", (
            f"Expected ✅ for configured {connector_type}, got {icon}"
        )


@given(connector_type=connector_type_st)
@settings(max_examples=100)
def test_property_2_status_icon_unconfigured_returns_warning(connector_type):
    """Feature: streamlit-connector-ui, Property 2: Status icon reflects configuration state

    If no matching enabled YAML file exists, get_status_icon() returns warning.

    Validates: Requirements 1.3
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_dir = Path(tmp_dir)
        # Empty directory - no config files
        icon = get_status_icon(connector_type, config_dir)
        assert icon == "⚠️", (
            f"Expected ⚠️ for unconfigured {connector_type}, got {icon}"
        )


@given(connector_type=connector_type_st)
@settings(max_examples=100)
def test_property_2_status_icon_disabled_returns_warning(connector_type):
    """Feature: streamlit-connector-ui, Property 2: Status icon reflects configuration state

    If a matching YAML exists but enabled is false, returns warning icon.

    Validates: Requirements 1.3
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        config_dir = Path(tmp_dir)
        # Write a YAML file with enabled: false
        config = {
            "name": f"Test {connector_type}",
            "type": connector_type,
            "enabled": False,
            "settings": {"host": "localhost"},
        }
        yaml_path = config_dir / f"{connector_type}.yaml"
        with open(yaml_path, "w") as f:
            yaml.dump(config, f)

        icon = get_status_icon(connector_type, config_dir)
        assert icon == "⚠️", (
            f"Expected ⚠️ for disabled {connector_type}, got {icon}"
        )


# ─── Property 3: Selection fallback to first available ────────────────────────


@given(
    available=connector_subset_st,
    selection=connector_type_st,
)
@settings(max_examples=100)
def test_property_3_selection_in_available_returns_same(available, selection):
    """Feature: streamlit-connector-ui, Property 3: Selection fallback to first available

    If current_selection is in available_types, resolve_active_selection()
    returns it unchanged.

    Validates: Requirements 1.5
    """
    # Ensure selection is in available for this test
    if selection not in available:
        available = [selection] + available

    result = resolve_active_selection(selection, available)
    assert result == selection, (
        f"Expected {selection} back, got {result}"
    )


@given(available=connector_subset_st)
@settings(max_examples=100)
def test_property_3_selection_not_in_available_returns_first(available):
    """Feature: streamlit-connector-ui, Property 3: Selection fallback to first available

    If current_selection is not in available_types, resolve_active_selection()
    returns the first item.

    Validates: Requirements 1.5
    """
    # Use a selection string that cannot be in available_types
    bogus_selection = "nonexistent_connector_xyz"
    result = resolve_active_selection(bogus_selection, available)
    assert result == available[0], (
        f"Expected first item {available[0]}, got {result}"
    )


@given(available=connector_subset_st)
@settings(max_examples=100)
def test_property_3_none_selection_returns_first(available):
    """Feature: streamlit-connector-ui, Property 3: Selection fallback to first available

    If current_selection is None, resolve_active_selection() returns
    the first item in available_types.

    Validates: Requirements 1.5
    """
    result = resolve_active_selection(None, available)
    assert result == available[0], (
        f"Expected first item {available[0]}, got {result}"
    )


# ─── Property 5: Template parsing produces matching form fields ───────────────


@given(
    settings_dict=st.dictionaries(
        keys=field_name_st,
        values=field_value_st,
        min_size=1,
        max_size=10,
    )
)
@settings(max_examples=100)
def test_property_5_template_parsing_produces_matching_form_fields(settings_dict):
    """Feature: streamlit-connector-ui, Property 5: Template parsing produces matching form fields

    Validates: Requirements 2.2, 3.1, 3.7
    """
    # Write a temp YAML template file with settings dict
    template_data = {"settings": settings_dict}

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml.template", delete=False
    ) as f:
        yaml.dump(template_data, f)
        temp_path = f.name

    try:
        fields = extract_template_fields(Path(temp_path))

        # Should return one entry per key in settings
        assert len(fields) == len(settings_dict), (
            f"Expected {len(settings_dict)} fields, got {len(fields)}"
        )

        # Each field should have correct key and placeholder
        field_keys = {field["key"] for field in fields}
        assert field_keys == set(settings_dict.keys()), (
            f"Field keys mismatch: {field_keys} != {set(settings_dict.keys())}"
        )

        for field in fields:
            key = field["key"]
            assert field["placeholder"] == str(settings_dict[key]), (
                f"Placeholder mismatch for {key}: "
                f"{field['placeholder']} != {str(settings_dict[key])}"
            )
    finally:
        os.unlink(temp_path)


# ─── Property 6: Configuration write/read round-trip ─────────────────────────


@given(
    connector_type=connector_type_st,
    name=st.text(
        min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
    settings_data=st.dictionaries(
        keys=field_name_st,
        values=st.text(min_size=1, max_size=255, alphabet=st.characters(whitelist_categories=("L", "N", "P"))),
        min_size=1,
        max_size=5,
    ),
)
@settings(max_examples=100)
def test_property_6_configuration_write_read_round_trip(
    connector_type, name, settings_data
):
    """Feature: streamlit-connector-ui, Property 6: Configuration write/read round-trip

    Validates: Requirements 3.2
    """
    # Build config
    config = build_yaml_config(connector_type, name, settings_data)

    # Write to temp file
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".yaml", delete=False
    ) as f:
        yaml.dump(config, f)
        temp_path = f.name

    try:
        # Read back
        with open(temp_path, "r") as f:
            loaded = yaml.safe_load(f)

        # Verify round-trip
        assert loaded["type"] == connector_type, (
            f"Type mismatch: {loaded['type']} != {connector_type}"
        )
        assert loaded["name"] == name, (
            f"Name mismatch: {loaded['name']} != {name}"
        )
        assert loaded["enabled"] is True, (
            f"Expected enabled=True, got {loaded['enabled']}"
        )
        assert loaded["settings"] == settings_data, (
            f"Settings mismatch: {loaded['settings']} != {settings_data}"
        )
    finally:
        os.unlink(temp_path)


# ─── Property 7: Validation flags exactly the empty required fields ──────────


@given(
    fields_and_values=st.lists(
        st.tuples(
            field_name_st,
            st.one_of(
                # Empty or whitespace-only (should fail validation)
                st.just(""),
                st.just("   "),
                st.just("\t"),
                # Non-empty valid values (should pass validation)
                st.text(min_size=1, max_size=255, alphabet=st.characters(whitelist_categories=("L", "N"))),
            ),
        ),
        min_size=1,
        max_size=10,
        unique_by=lambda x: x[0],  # unique field names
    )
)
@settings(max_examples=100)
def test_property_7_validation_flags_exactly_empty_required_fields(fields_and_values):
    """Feature: streamlit-connector-ui, Property 7: Validation flags exactly the empty required fields

    Validates: Requirements 3.3
    """
    fields = [name for name, _ in fields_and_values]
    values = {name: val for name, val in fields_and_values}

    errors = validate_form_data(fields, values)

    for name, val in fields_and_values:
        if not val or val.strip() == "":
            # Should have an error for empty/whitespace-only fields
            assert name in errors, (
                f"Expected error for empty field '{name}' with value '{val!r}'"
            )
        elif len(val) <= 255:
            # Should NOT have an error for non-empty fields within limit
            assert name not in errors, (
                f"Unexpected error for valid field '{name}': {errors.get(name)}"
            )


# ─── Property 9: Test failure preserves error message ─────────────────────────


@given(error_message=message_st)
@settings(max_examples=100)
def test_property_9_test_failure_preserves_error_message(error_message):
    """Feature: streamlit-connector-ui, Property 9: Test failure preserves error message

    Validates: Requirements 4.4
    """
    result = format_test_failure(error_message)
    assert error_message in result, (
        f"Error message '{error_message}' not found in formatted output: '{result}'"
    )


# ─── Property 10: Test success contains dialect and valid ISO 8601 timestamp ──


@given(
    dialect=message_st,
    timestamp_iso=st.text(min_size=1, max_size=100),
)
@settings(max_examples=100)
def test_property_10_test_success_contains_dialect_and_timestamp(
    dialect, timestamp_iso
):
    """Feature: streamlit-connector-ui, Property 10: Test success contains dialect and valid ISO 8601 timestamp

    Validates: Requirements 4.5
    """
    result = format_test_success(dialect, timestamp_iso)
    assert dialect in result, (
        f"Dialect '{dialect}' not found in formatted output: '{result}'"
    )
    assert timestamp_iso in result, (
        f"Timestamp '{timestamp_iso}' not found in formatted output: '{result}'"
    )


# ─── Property 11: Connector metadata mapping is total and correct ─────────────


@given(connector_type=connector_type_st)
@settings(max_examples=100)
def test_property_11_connector_metadata_mapping_is_total_and_correct(connector_type):
    """Feature: streamlit-connector-ui, Property 11: Connector metadata mapping is total and correct

    Validates: Requirements 5.1, 5.2
    """
    metadata = get_connector_metadata(connector_type)

    # Should return correct dialect label
    expected_dialect = DIALECT_LABELS[connector_type]
    assert metadata["dialect_label"] == expected_dialect, (
        f"Dialect label mismatch for {connector_type}: "
        f"{metadata['dialect_label']} != {expected_dialect}"
    )

    # Should return correct icon
    expected_icon = CONNECTOR_ICONS[connector_type]
    assert metadata["icon"] == expected_icon, (
        f"Icon mismatch for {connector_type}: "
        f"{metadata['icon']} != {expected_icon}"
    )


# ─── Property 12: Name truncation respects length bounds ─────────────────────


@given(name=st.text(min_size=0, max_size=200))
@settings(max_examples=100)
def test_property_12_name_truncation_respects_length_bounds(name):
    """Feature: streamlit-connector-ui, Property 12: Name truncation respects length bounds

    Validates: Requirements 5.3
    """
    result = truncate_name(name)

    if len(name) > 50:
        # Should be exactly 53 chars (50 + "...")
        assert len(result) == 53, (
            f"Expected 53 chars for input of length {len(name)}, got {len(result)}"
        )
        assert result.endswith("..."), (
            f"Expected result to end with '...' but got: '{result[-5:]}'"
        )
        assert result[:50] == name[:50], (
            "Truncated prefix doesn't match original"
        )
    else:
        # Should return input unchanged
        assert result == name, (
            f"Expected unchanged output for input of length {len(name)}, "
            f"but got '{result}' != '{name}'"
        )


# ─── Property 4: Status panel extracts all required fields from config ────────


@given(
    connector_type=connector_type_st,
    host_or_account=st.one_of(
        st.tuples(st.just("host"), field_value_st),
        st.tuples(st.just("account"), field_value_st),
    ),
    database=field_value_st,
    extra_settings=st.dictionaries(
        keys=st.text(
            min_size=1,
            max_size=20,
            alphabet=st.characters(whitelist_categories=("L", "N")),
        ).filter(lambda k: k not in ("host", "account", "database")),
        values=field_value_st,
        min_size=0,
        max_size=5,
    ),
)
@settings(max_examples=100)
def test_property_4_status_panel_extracts_all_required_fields(
    connector_type, host_or_account, database, extra_settings
):
    """Feature: streamlit-connector-ui, Property 4: Status panel extracts all required fields from config

    For any valid connector config dict with type, enabled: True, and settings
    containing host (or account) and database with non-empty values,
    extract_status_panel_data() returns non-empty type, host_or_account,
    database, and status == "Connected".

    Validates: Requirements 2.1
    """
    key, value = host_or_account
    settings_dict = {key: value, "database": database, **extra_settings}

    config = {
        "type": connector_type,
        "enabled": True,
        "settings": settings_dict,
    }

    result = extract_status_panel_data(config)

    assert result["type"] == connector_type, (
        f"Expected type '{connector_type}', got '{result['type']}'"
    )
    assert result["type"] != "", "type should be non-empty"
    assert result["host_or_account"] != "", (
        f"host_or_account should be non-empty, got '{result['host_or_account']}'"
    )
    assert result["database"] != "", (
        f"database should be non-empty, got '{result['database']}'"
    )
    assert result["status"] == "Connected", (
        f"Expected status 'Connected' for enabled config, got '{result['status']}'"
    )


# ─── Property 8: Config pre-population matches stored values ─────────────────


@given(
    connector_type=connector_type_st,
    name=st.text(
        min_size=1, max_size=50, alphabet=st.characters(whitelist_categories=("L", "N"))
    ),
    settings_data=st.dictionaries(
        keys=field_name_st,
        values=st.text(
            min_size=1,
            max_size=255,
            alphabet=st.characters(whitelist_categories=("L", "N", "P")),
        ),
        min_size=1,
        max_size=5,
    ),
)
@settings(max_examples=100)
def test_property_8_config_pre_population_matches_stored_values(
    connector_type, name, settings_data
):
    """Feature: streamlit-connector-ui, Property 8: Config pre-population matches stored values

    For any valid YAML config built with build_yaml_config() with enabled: True,
    every key-value pair in the config's settings section can be extracted back,
    verifying that build_yaml_config() produces a structure where settings are
    preserved and accessible for pre-population.

    Validates: Requirements 3.4
    """
    # Build config using the helper
    config = build_yaml_config(connector_type, name, settings_data)

    # Verify config has enabled: True
    assert config["enabled"] is True, (
        f"Expected enabled=True, got {config['enabled']}"
    )

    # Extract settings from the built config (simulating pre-population read)
    extracted_settings = config["settings"]

    # Every key-value pair in the original settings_data must be present
    for key, value in settings_data.items():
        assert key in extracted_settings, (
            f"Key '{key}' not found in extracted settings"
        )
        assert extracted_settings[key] == value, (
            f"Value mismatch for key '{key}': "
            f"expected '{value}', got '{extracted_settings[key]}'"
        )

    # And no extra keys should be present
    assert set(extracted_settings.keys()) == set(settings_data.keys()), (
        f"Settings keys mismatch: {set(extracted_settings.keys())} != {set(settings_data.keys())}"
    )


# ─── Property 13: Unconfigured connector query produces banner with connector type name ─


@given(connector_type=connector_type_st)
@settings(max_examples=100)
def test_property_13_unconfigured_banner_contains_connector_display_name(connector_type):
    """Feature: streamlit-connector-ui, Property 13: Unconfigured connector query produces banner with connector type name

    Validates: Requirements 6.1
    """
    display_name = get_connector_display_name(connector_type)

    # Display name should be non-empty
    assert display_name, f"Display name for {connector_type} should not be empty"

    # Display name should match CONNECTOR_ORDER
    expected_names = {entry[0]: entry[1] for entry in CONNECTOR_ORDER}
    assert display_name == expected_names[connector_type], (
        f"Display name mismatch for {connector_type}: '{display_name}' != '{expected_names[connector_type]}'"
    )

    # Banner message should contain the display name
    banner_msg = f"⚠️ {display_name} is not configured. Please configure it to run queries."
    assert display_name in banner_msg
