"""Runtime schema inspection (Layer 6).

Shows both schemas:
- public: Company data (read-only for agents)
- dash: Agent-managed data (views, summaries, computed tables)
"""

from agno.tools import tool
from agno.utils.log import logger
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import DatabaseError, OperationalError

from db.session import DASH_SCHEMA

SCHEMAS = ["public", DASH_SCHEMA]


def create_introspect_schema_tool(db_url: str):
    """Create introspect_schema tool with database connection."""
    engine = create_engine(db_url)

    @tool
    def introspect_schema(
        table_name: str | None = None,
        schema: str | None = None,
        include_sample_data: bool = False,
        sample_limit: int = 5,
    ) -> str:
        """Inspect database schema at runtime.

        Args:
            table_name: Table to inspect. If None, lists all tables.
            schema: Filter to a specific schema ("public" or "dash"). If None, shows both.
            include_sample_data: Include sample rows.
            sample_limit: Number of sample rows.
        """
        try:
            insp = inspect(engine)
            schemas = [schema] if schema and schema in SCHEMAS else SCHEMAS

            if table_name is None:
                # List all tables across schemas
                lines: list[str] = []
                for s in schemas:
                    tables = insp.get_table_names(schema=s)
                    if not tables:
                        lines.append(f"## {s} (empty)")
                        lines.append("")
                        continue

                    label = "company data — read only" if s == "public" else "agent-managed"
                    lines.append(f"## {s} ({label})")
                    lines.append("")
                    for t in sorted(tables):
                        try:
                            with engine.connect() as conn:
                                count = conn.execute(text(f'SELECT COUNT(*) FROM "{s}"."{t}"')).scalar()
                                lines.append(f"- **{s}.{t}** ({count:,} rows)")
                        except (OperationalError, DatabaseError):
                            lines.append(f"- **{s}.{t}**")
                    lines.append("")
                return "\n".join(lines)

            # Inspect specific table — find which schema it's in
            found_schema = None
            for s in schemas:
                if table_name in insp.get_table_names(schema=s):
                    found_schema = s
                    break

            if found_schema is None:
                all_tables: list[str] = []
                for s in schemas:
                    all_tables.extend(f"{s}.{t}" for t in insp.get_table_names(schema=s))
                return f"Table '{table_name}' not found. Available: {', '.join(sorted(all_tables))}"

            label = "company data" if found_schema == "public" else "agent-managed"
            lines = [f"## {found_schema}.{table_name} ({label})", ""]

            # Columns
            cols = insp.get_columns(table_name, schema=found_schema)
            if cols:
                lines.extend(["### Columns", "", "| Column | Type | Nullable |", "| --- | --- | --- |"])
                for c in cols:
                    nullable = "Yes" if c.get("nullable", True) else "No"
                    lines.append(f"| {c['name']} | {c['type']} | {nullable} |")
                lines.append("")

            # Primary key
            pk = insp.get_pk_constraint(table_name, schema=found_schema)
            if pk and pk.get("constrained_columns"):
                lines.append(f"**Primary Key:** {', '.join(pk['constrained_columns'])}")
                lines.append("")

            # Sample data
            if include_sample_data:
                lines.append("### Sample")
                try:
                    with engine.connect() as conn:
                        result = conn.execute(
                            text(f'SELECT * FROM "{found_schema}"."{table_name}" LIMIT {sample_limit}')
                        )
                        rows = result.fetchall()
                        col_names = list(result.keys())
                        if rows:
                            lines.append("| " + " | ".join(col_names) + " |")
                            lines.append("| " + " | ".join(["---"] * len(col_names)) + " |")
                            for row in rows:
                                vals = [str(v)[:30] if v else "NULL" for v in row]
                                lines.append("| " + " | ".join(vals) + " |")
                        else:
                            lines.append("_No data_")
                except (OperationalError, DatabaseError) as e:
                    lines.append(f"_Error: {e}_")

            return "\n".join(lines)

        except OperationalError as e:
            logger.error(f"Database connection failed: {e}")
            return f"Error: Database connection failed - {e}"
        except DatabaseError as e:
            logger.error(f"Database error: {e}")
            return f"Error: {e}"

    return introspect_schema
