from __future__ import annotations

import httpx
import ibis
import ibis.expr.datatypes as dt

from .datatypes import path_to_column_name, path_to_ibis_type


class SignalKCatalog:
    def __init__(self, base_url: str, client: httpx.Client | None = None) -> None:
        self._base = base_url.rstrip("/")
        self._client = client or httpx.Client()
        self._paths_cache: dict[str, list[str]] = {}

    def paths(self, duration: str = "P1D") -> list[str]:
        if duration not in self._paths_cache:
            r = self._client.get(
                f"{self._base}/signalk/v2/api/history/paths",
                params={"duration": duration},
            )
            r.raise_for_status()
            self._paths_cache[duration] = r.json()
        return self._paths_cache[duration]

    def namespaces(self, duration: str = "P1D") -> list[str]:
        return sorted({p.split(".")[0] for p in self.paths(duration)})

    def schema_for(self, namespace: str, duration: str = "P1D") -> ibis.Schema:
        fields: dict[str, dt.DataType] = {"timestamp": dt.Timestamp(timezone="UTC")}
        for path in self.paths(duration):
            if path.split(".")[0] == namespace:
                fields[path_to_column_name(path)] = path_to_ibis_type(path)
        return ibis.schema(fields)

    def providers(self) -> dict[str, dict]:
        r = self._client.get(f"{self._base}/signalk/v2/api/history/_providers")
        r.raise_for_status()
        return r.json()
