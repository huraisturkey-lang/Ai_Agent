"""Abstract base class for all data source connectors."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseConnector(ABC):
    """Interface that every data source connector must implement.

    A connector knows how to:
    1. Discover schema (tables + columns) from the data source
    2. Execute read-only SQL queries
    3. Report its SQL dialect so the LLM generates correct syntax
    4. Run full LLM-powered natural language queries (question → SQL → answer)
    """

    def __init__(self, name: str, settings: dict[str, Any]):
        self.name = name
        self.settings = settings
        self._llm_service = None

    @property
    @abstractmethod
    def dialect(self) -> str:
        """SQL dialect identifier (e.g. 'athena', 'postgresql', 'snowflake', 'spark').

        Used in the LLM prompt to generate correct SQL syntax.
        """

    @abstractmethod
    def get_schema(self) -> tuple[str, set[str]]:
        """Discover the schema from the data source.

        Returns:
            A tuple of (catalog_string, allowed_tables) where:
            - catalog_string: pipe-delimited rows like "database|table|column_name"
            - allowed_tables: set of table names the LLM is allowed to query
        """

    @abstractmethod
    def execute_sql(self, sql: str) -> list[dict[str, Any]]:
        """Execute a read-only SQL query and return results as list of dicts.

        Args:
            sql: The SQL query to execute (must be read-only).

        Returns:
            List of row dictionaries.

        Raises:
            RuntimeError: If the query fails or is not read-only.
        """

    def run_query(self, question: str) -> str:
        """Full LLM-powered query: natural language → SQL → execute → answer.

        Uses the connector's own schema and execute_sql method with
        LLMSQLService for Bedrock-powered SQL generation and answering.
        """
        service = self._get_llm_service()
        return service.run_query(question)

    def _get_llm_service(self):
        """Lazy-build an LLMSQLService backed by this connector."""
        if self._llm_service is None:
            from llm_sql.core import LLMSQLService
            from llm_sql.config import get_settings

            settings = get_settings()
            catalog, allowed_tables = self.get_schema()

            # Wrap this connector in a db-like object with a run() method
            db_adapter = _ConnectorDBAdapter(self)

            self._llm_service = LLMSQLService(
                db=db_adapter,
                glue_catalog=catalog,
                allowed_tables=allowed_tables,
                bedrock_model=settings.bedrock_model,
                region=settings.region,
                max_retries=settings.bedrock_max_retries,
                retry_base_delay=settings.bedrock_retry_base_delay,
                secrets_manager_secret=settings.secrets_manager_secret,
                max_result_rows=settings.max_result_rows,
                max_question_chars=settings.max_question_chars,
            )
        return self._llm_service

    def test_connection(self) -> bool:
        """Test if the connection is working.

        Returns:
            True if connection is healthy, False otherwise.
        """
        try:
            self.get_schema()
            return True
        except Exception:
            return False

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.name!r} dialect={self.dialect!r}>"


class _ConnectorDBAdapter:
    """Adapts a BaseConnector's execute_sql() to the db.run() interface
    expected by LLMSQLService."""

    def __init__(self, connector: BaseConnector):
        self._connector = connector

    def run(self, sql: str):
        return self._connector.execute_sql(sql)
