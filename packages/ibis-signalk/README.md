# ibis-signalk

An Ibis backend for the [SignalK](https://signalk.org/) History API. Lets Marimo's
Data Sources panel (and plain Ibis code) browse, query and extract SignalK history
data with aggregation and resolution pushed down to the server — no local storage,
no DuckDB import step.

See `../../planning/data_connectivity.md` in the parent repo for the design notes.

## Local dev

Iterate against a real SignalK server (no browser/WASM round-trip needed):

```sh
cd packages/ibis-signalk
SIGNALK_URL=http://<boat-host>:<port> uv run marimo edit notebooks/dev.py
```

Defaults to `http://10.36.10.20` if `SIGNALK_URL` is unset.

