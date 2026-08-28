from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

import ibis.expr.operations as ops

from .datatypes import column_name_to_path


@dataclass
class HistoryRequest:
    """Direct mapping to History V2 `/values` query parameters."""

    paths: list[str] = field(default_factory=list)  # path[:method[:param]]
    from_: datetime | None = None
    to: datetime | None = None
    duration: str | None = None  # ISO 8601 duration, e.g. PT1H
    resolution: str | None = None  # seconds, or "1s"/"1m"/"1h"/"1d"
    context: str = "vessels.self"
    provider: str | None = None
    # Output column names, in the same order as `paths` — the ibis-expected
    # aliases, which may differ from the raw path (e.g. `by=[...]` group
    # aliases, or `.select(alias=col)` renames).
    column_names: list[str] = field(default_factory=list)
    timestamp_name: str = "timestamp"

    def to_params(self) -> dict[str, str]:
        p: dict[str, str] = {"paths": ",".join(self.paths)}
        if self.from_ is not None:
            p["from"] = self.from_.isoformat()
        if self.to is not None:
            p["to"] = self.to.isoformat()
        if self.duration:
            p["duration"] = self.duration
        if self.resolution:
            p["resolution"] = self.resolution
        if self.context != "vessels.self":
            p["context"] = self.context
        if self.provider:
            p["provider"] = self.provider
        return p


# Ibis reduction op class name -> SignalK History API method string
_AGG_METHOD: dict[str, str] = {
    "Mean": "average",
    "Min": "min",
    "Max": "max",
    "First": "first",
    "Last": "last",
}

# ops.TimestampTruncate unit name -> SignalK `resolution` string
_TRUNCATE_RESOLUTION: dict[str, str] = {
    "SECOND": "1s",
    "MINUTE": "1m",
    "HOUR": "1h",
    "DAY": "1d",
}


class SignalKCompiler:
    """Walks an Ibis op tree and produces a `HistoryRequest`.

    Only understands the operations the History API can push down server-side:
    plain column projection, timestamp range filters, and aggregation
    (optionally grouped by a truncated timestamp -> `resolution`). Anything
    else (joins, arbitrary scalar expressions, non-timestamp filters) is
    rejected rather than silently pulled client-side, since this backend has
    no local execution engine to fall back on.
    """

    def compile(self, node: ops.Node) -> HistoryRequest:
        req = HistoryRequest()
        self._visit(node, req)
        if not req.paths:
            names = [name for name in node.schema.names if name != "timestamp"]
            req.paths = [column_name_to_path(name) for name in names]
            req.column_names = names
        return req

    def _visit(self, op: ops.Node, req: HistoryRequest) -> None:
        if isinstance(op, (ops.UnboundTable, ops.DatabaseTable)):
            return
        if isinstance(op, ops.Project):
            self._visit(op.parent, req)
            self._apply_projection(op, req)
        elif isinstance(op, ops.Filter):
            self._visit(op.parent, req)
            self._apply_filters(op, req)
        elif isinstance(op, ops.Aggregate):
            self._visit(op.parent, req)
            self._apply_aggregate(op, req)
        else:
            raise NotImplementedError(
                f"signalk backend cannot push down {type(op).__name__!r}"
            )

    def _apply_projection(self, op: ops.Project, req: HistoryRequest) -> None:
        paths = []
        names = []
        for alias, value in op.values.items():
            if not isinstance(value, ops.Field):
                raise NotImplementedError(
                    f"signalk backend can only push down plain column selections, "
                    f"got {type(value).__name__!r} for {alias!r}"
                )
            if value.name == "timestamp":
                req.timestamp_name = alias
                continue
            paths.append(column_name_to_path(value.name))
            names.append(alias)
        if paths:
            req.paths = paths
            req.column_names = names

    def _apply_filters(self, op: ops.Filter, req: HistoryRequest) -> None:
        for pred in op.predicates:
            if not (isinstance(pred.left, ops.Field) and pred.left.name == "timestamp"):
                raise NotImplementedError(
                    "signalk backend can only push down filters on the timestamp column"
                )
            value = _literal_value(pred.right)
            if isinstance(pred, (ops.Greater, ops.GreaterEqual)):
                req.from_ = value
            elif isinstance(pred, (ops.Less, ops.LessEqual)):
                req.to = value
            else:
                raise NotImplementedError(
                    f"signalk backend cannot push down filter {type(pred).__name__!r}"
                )

    def _apply_aggregate(self, op: ops.Aggregate, req: HistoryRequest) -> None:
        paths = []
        names = []
        for alias, metric in op.metrics.items():
            if not isinstance(metric, ops.Reduction) or not hasattr(metric, "arg"):
                raise NotImplementedError(
                    f"signalk backend cannot push down aggregation {type(metric).__name__!r}"
                )
            method = _AGG_METHOD.get(type(metric).__name__)
            if method is None:
                raise NotImplementedError(
                    f"signalk backend has no pushdown for aggregation {type(metric).__name__!r}"
                )
            paths.append(f"{column_name_to_path(metric.arg.name)}:{method}")
            names.append(alias)
        if paths:
            req.paths = paths
            req.column_names = names

        for alias, group in op.groups.items():
            if isinstance(group, ops.TimestampTruncate):
                req.resolution = _TRUNCATE_RESOLUTION.get(group.unit.name, "1m")
                req.timestamp_name = alias


def _literal_value(op: ops.Node) -> datetime | str:
    if isinstance(op, ops.Literal):
        return op.value
    if isinstance(op, ops.Cast):
        return _literal_value(op.arg)
    raise NotImplementedError(
        f"signalk backend can only push down literal filter values, got {type(op).__name__!r}"
    )
