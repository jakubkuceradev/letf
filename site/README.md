# Article site

`index.html` is the draft article with the interactive chart. It is a static page: no build step and no server code.

To build the data and view the page:

```sh
uv run python scripts/run_all.py      # simulation results (about 40 s)
uv run python scripts/build_site.py   # copies chart JSON into site/data and writes summary.json
cd site && python -m http.server 8000 # then open http://localhost:8000
```

`site/data/` is generated and not committed (about 110 MB). Every number in the article text comes from `data/summary.json`, so rerunning both scripts updates the prose and the chart together.

The chart uses [Observable Plot](https://observablehq.com/plot/) 0.6.16 and d3 7.9.0, vendored in `vendor/` with their licenses.
