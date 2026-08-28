import marimo

__generated_with = "0.23.8"
app = marimo.App(width="full", app_title="ibis-signalk dev")


@app.cell(hide_code=True)
def _():
    import marimo as mo
    import os

    signalk_url = os.environ.get("SIGNALK_URL", "http://10.36.10.20")
    mo.md(f"# ibis-signalk dev notebook\nTarget server: `{signalk_url}`")
    return mo, signalk_url


@app.cell(hide_code=True)
def _(signalk_url):
    from ibis_signalk import Backend

    con = Backend()
    con.do_connect(signalk_url)
    return (con,)


@app.cell
def _(con):
    namespaces = con.list_tables()
    namespaces
    return (namespaces,)


@app.cell
def _(mo, namespaces):
    namespace_picker = mo.ui.dropdown(options=namespaces, value=namespaces[0], label="Namespace")
    namespace_picker
    return (namespace_picker,)


@app.cell
def _(con, namespace_picker):
    t = con.table(namespace_picker.value)
    t.schema()
    return (t,)


@app.cell
def _(mo):
    duration_seconds = mo.ui.slider(10, 600, value=60, step=10, label="Lookback window (seconds)")
    resolution = mo.ui.dropdown(options=["s", "m", "h"], value="s", label="Aggregate resolution")
    mo.hstack([duration_seconds, resolution])
    return duration_seconds, resolution


@app.cell
def _(con, duration_seconds, resolution, t):
    from datetime import datetime, timedelta, timezone

    _now = datetime.now(timezone.utc)
    _windowed = t.filter(
        t.timestamp >= _now - timedelta(seconds=duration_seconds.value),
        t.timestamp <= _now,
    )

    _numeric_cols = [
        name for name, dtype in t.schema().items() if name != "timestamp" and dtype.is_numeric()
    ]
    _metrics = {col: _windowed[col].mean() for col in _numeric_cols}

    aggregated = _windowed.aggregate(
        **_metrics,
        by=[_windowed.timestamp.truncate(resolution.value).name("timestamp")],
    )
    con.execute(aggregated)
    return


if __name__ == "__main__":
    app.run()
