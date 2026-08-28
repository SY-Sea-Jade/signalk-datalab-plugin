from __future__ import annotations

from typing import Any, Mapping

import ibis.expr.operations as ops
import ibis.expr.types as ir
import pyarrow as pa
from ibis import Schema
from ibis.backends import BaseBackend

from .catalog import SignalKCatalog
from .compiler import HistoryRequest, SignalKCompiler
from .transport import SignalKTransport


class Backend(BaseBackend):
    """Read-only Ibis backend over the SignalK History API.

    There's no local execution engine here — every expression must compile
    down to a single History API request (`SignalKCompiler`), since
    aggregation and time-range filtering only happen server-side.
    """

    name = "signalk"
    dialect = None
    supports_temporary_tables = False
    supports_python_udfs = False

    def do_connect(self, base_url: str) -> None:
        self.catalog = SignalKCatalog(base_url)
        self._transport = SignalKTransport(base_url)
        self._compiler = SignalKCompiler()

    def disconnect(self) -> None:
        pass

    @property
    def version(self) -> str:
        return "0.1.0"

    def list_tables(
        self, *, like: str | None = None, database: str | None = None
    ) -> list[str]:
        names = self.catalog.namespaces()
        return self._filter_with_like(names, like) if like else names

    def table(self, name: str, /, *, database: str | None = None) -> ir.Table:
        schema = self.catalog.schema_for(name)
        return ops.DatabaseTable(name, schema, self).to_expr()

    def get_schema(self, table_name: str, /, *, database: str | None = None) -> Schema:
        return self.catalog.schema_for(table_name)

    def compile(
        self,
        expr: ir.Expr,
        /,
        *,
        limit: int | None = None,
        params: Mapping[ir.Expr, Any] | None = None,
        **kwargs: Any,
    ) -> HistoryRequest:
        node = expr.as_table().op()
        return self._compiler.compile(node)

    def to_pyarrow(
        self,
        expr: ir.Expr,
        /,
        *,
        params: Mapping[ir.Expr, Any] | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ) -> pa.Table:
        req = self.compile(expr, limit=limit, params=params, **kwargs)
        table = self._transport.fetch(req)
        return expr.__pyarrow_result__(table)

    def execute(
        self,
        expr: ir.Expr,
        /,
        *,
        params: Mapping[ir.Expr, Any] | None = None,
        limit: int | None = None,
        **kwargs: Any,
    ):
        table = self.to_pyarrow(expr, params=params, limit=limit, **kwargs)
        return expr.__pandas_result__(table.to_pandas())

    def _register_in_memory_table(self, op: ops.InMemoryTable) -> None:
        raise NotImplementedError("signalk backend is read-only")

    def _make_memtable_finalizer(self, name: str):
        return None

    def create_table(
        self,
        name: str,
        /,
        obj=None,
        *,
        schema: Schema | None = None,
        database: str | None = None,
        temp: bool = False,
        overwrite: bool = False,
    ) -> ir.Table:
        raise NotImplementedError("signalk backend is read-only")

    def create_view(
        self,
        name: str,
        /,
        obj: ir.Table,
        *,
        database: str | None = None,
        overwrite: bool = False,
    ) -> ir.Table:
        raise NotImplementedError("signalk backend is read-only")

    def drop_view(
        self, name: str, /, *, database: str | None = None, force: bool = False
    ) -> None:
        raise NotImplementedError("signalk backend is read-only")

    def drop_table(
        self, name: str, /, *, database: str | None = None, force: bool = False
    ) -> None:
        raise NotImplementedError("signalk backend is read-only")
