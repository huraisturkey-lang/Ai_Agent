"""Unit tests for scripts/sidebar_helpers.py.

Validates: Requirements 1.1, 1.3, 2.1, 3.1, 3.2, 3.3, 5.3
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Ensure project root is importable
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from scripts.sidebar_helpers import (
    build_yaml_config,
    extract_status_panel_data,
    extract_template_fields,
    get_status_icon,
    group_connectors,
    truncate_name,
    validate_form_data,
)


class TestGroupConnectors(unittest.TestCase):
    """Test group_connectors with various inputs."""

    def test_group_connectors_all_types(self):
        """Pass all 6 types. Verify correct two groups in fixed display order."""
        all_types = ["athena", "redshift", "rds_postgres", "rds_mysql", "snowflake", "databricks"]
        result = group_connectors(all_types)

        self.assertEqual(
            result["AWS Native"],
            ["athena", "redshift", "rds_postgres", "rds_mysql"],
        )
        self.assertEqual(
            result["External Platforms"],
            ["snowflake", "databricks"],
        )

    def test_group_connectors_subset(self):
        """Pass only a subset. Verify correct grouping."""
        result = group_connectors(["snowflake", "athena"])

        self.assertEqual(result["AWS Native"], ["athena"])
        self.assertEqual(result["External Platforms"], ["snowflake"])


class TestGetStatusIcon(unittest.TestCase):
    """Test get_status_icon for various config states."""

    def test_get_status_icon_configured(self):
        """YAML with enabled: true returns green checkmark."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "redshift.yaml"
            config_path.write_text("type: redshift\nenabled: true\n")

            result = get_status_icon("redshift", Path(tmpdir))
            self.assertEqual(result, "✅")

    def test_get_status_icon_unconfigured(self):
        """No matching file returns warning icon."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = get_status_icon("redshift", Path(tmpdir))
            self.assertEqual(result, "⚠️")

    def test_get_status_icon_disabled(self):
        """YAML with enabled: false returns warning icon."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "redshift.yaml"
            config_path.write_text("type: redshift\nenabled: false\n")

            result = get_status_icon("redshift", Path(tmpdir))
            self.assertEqual(result, "⚠️")


class TestExtractTemplateFields(unittest.TestCase):
    """Test extract_template_fields against real template files."""

    def test_extract_template_fields_redshift(self):
        """Real redshift template returns expected settings fields."""
        template_path = Path(project_root) / "config" / "connections" / "redshift.yaml.template"
        if not template_path.exists():
            self.skipTest("redshift.yaml.template not found")

        fields = extract_template_fields(template_path)
        field_keys = [f["key"] for f in fields]

        for expected_key in ["host", "port", "database", "schema", "user_from_secret", "region"]:
            self.assertIn(expected_key, field_keys)

    def test_extract_template_fields_snowflake(self):
        """Real snowflake template returns expected settings fields."""
        template_path = Path(project_root) / "config" / "connections" / "snowflake.yaml.template"
        if not template_path.exists():
            self.skipTest("snowflake.yaml.template not found")

        fields = extract_template_fields(template_path)
        field_keys = [f["key"] for f in fields]

        for expected_key in ["account", "warehouse", "database", "schema", "role", "user_from_secret"]:
            self.assertIn(expected_key, field_keys)


class TestValidateFormData(unittest.TestCase):
    """Test validate_form_data boundary cases."""

    def test_validate_form_data_empty(self):
        """Empty field value produces error for that field only."""
        fields = ["host", "port"]
        values = {"host": "", "port": "5439"}

        errors = validate_form_data(fields, values)

        self.assertIn("host", errors)
        self.assertNotIn("port", errors)

    def test_validate_form_data_255_valid(self):
        """Field value of exactly 255 chars passes validation."""
        fields = ["host"]
        values = {"host": "a" * 255}

        errors = validate_form_data(fields, values)

        self.assertEqual(errors, {})

    def test_validate_form_data_256_invalid(self):
        """Field value of 256 chars produces an error."""
        fields = ["host"]
        values = {"host": "a" * 256}

        errors = validate_form_data(fields, values)

        self.assertIn("host", errors)


class TestTruncateName(unittest.TestCase):
    """Test truncate_name at boundary lengths."""

    def test_truncate_name_50_chars(self):
        """String of exactly 50 chars returns unchanged."""
        name = "a" * 50
        result = truncate_name(name)
        self.assertEqual(result, name)
        self.assertEqual(len(result), 50)

    def test_truncate_name_51_chars(self):
        """String of 51 chars returns first 50 chars + '...' (total 53)."""
        name = "a" * 51
        result = truncate_name(name)
        self.assertEqual(result, "a" * 50 + "...")
        self.assertEqual(len(result), 53)


class TestExtractStatusPanelData(unittest.TestCase):
    """Test extract_status_panel_data for different config types."""

    def test_extract_status_panel_data_external(self):
        """Config with host and database extracts all fields correctly."""
        config = {
            "type": "redshift",
            "enabled": True,
            "settings": {
                "host": "my-cluster.eu-north-1.redshift.amazonaws.com",
                "database": "analytics",
            },
        }

        result = extract_status_panel_data(config)

        self.assertEqual(result["type"], "redshift")
        self.assertEqual(result["host_or_account"], "my-cluster.eu-north-1.redshift.amazonaws.com")
        self.assertEqual(result["database"], "analytics")
        self.assertEqual(result["status"], "Connected")

    def test_extract_status_panel_data_account_fallback(self):
        """Config with account (no host) uses account for host_or_account."""
        config = {
            "type": "snowflake",
            "enabled": True,
            "settings": {
                "account": "xy12345.eu-west-1",
                "database": "ANALYTICS",
            },
        }

        result = extract_status_panel_data(config)

        self.assertEqual(result["type"], "snowflake")
        self.assertEqual(result["host_or_account"], "xy12345.eu-west-1")
        self.assertEqual(result["database"], "ANALYTICS")
        self.assertEqual(result["status"], "Connected")


class TestBuildYamlConfig(unittest.TestCase):
    """Test build_yaml_config produces correct structure."""

    def test_build_yaml_config(self):
        """Verify structure has name, type, enabled=True, settings."""
        settings = {"host": "localhost", "port": "5439", "database": "mydb"}
        result = build_yaml_config("redshift", "My Redshift", settings)

        self.assertEqual(result["name"], "My Redshift")
        self.assertEqual(result["type"], "redshift")
        self.assertTrue(result["enabled"])
        self.assertEqual(result["settings"], settings)


if __name__ == "__main__":
    unittest.main()
