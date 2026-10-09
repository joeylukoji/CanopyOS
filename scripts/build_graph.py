"""Build a Graphify map of first-party application code, without model/API calls."""

import json
import sys
from pathlib import Path

from graphify.analyze import god_nodes, suggest_questions, surprising_connections
from graphify.build import build_from_json
from graphify.cluster import cluster, score_all
from graphify.detect import detect, save_manifest
from graphify.diagnostics import diagnose_extraction, format_diagnostic_report
from graphify.export import to_html, to_json
from graphify.extract import extract
from graphify.report import generate

root = Path(__file__).resolve().parents[1]
out = root / "graphify-out"
out.mkdir(exist_ok=True)
detection = detect(
    root / "app",
    extra_excludes=["templates", "*.css", "*.svg", "*.txt", "htmx.min.js"],
    cache_root=root,
)
files = [Path(f) for f in detection["files"].get("code", [])]
print(f"Corpus: {len(files)} first-party code files; deterministic AST only; no semantic API cost.")
extraction = extract(files, cache_root=root)
graph = build_from_json(extraction, root=str(root), directed=True)
if not graph.number_of_nodes():
    raise SystemExit("Empty graph; no output overwritten.")
communities = cluster(graph)
cohesion = score_all(graph, communities)
names_by_id = {
    0: "Analysis and metrics",
    1: "HTTP scan lifecycle",
    2: "Decisions and explanations",
    3: "Application dependencies",
    4: "Private scan storage",
    5: "Browser camera flow",
    6: "SegFormer inference",
    7: "Application package",
    8: "Service package",
}
labels = {}
for cid, nodes in communities.items():
    names = [graph.nodes[n].get("label", str(n)) for n in nodes]
    labels[cid] = names_by_id.get(cid, " / ".join(names[:2]))
    print(f"Community {cid}: {names}")
if not to_json(graph, communities, str(out / "graph.json"), community_labels=labels):
    raise SystemExit("Graphify refused to overwrite a larger graph.")
diagnosis = diagnose_extraction(extraction, directed=True, root=str(root))
print(format_diagnostic_report(diagnosis))
gods = god_nodes(graph)
surprises = surprising_connections(graph, communities)
questions = suggest_questions(graph, communities, labels)
report = generate(
    graph,
    communities,
    cohesion,
    labels,
    gods,
    surprises,
    detection,
    {"input": 0, "output": 0},
    str(root),
    suggested_questions=questions,
)
(out / "GRAPH_REPORT.md").write_text(report, encoding="utf-8")
to_html(graph, communities, str(out / "graph.html"), community_labels=labels)
save_manifest({"code": [str(p) for p in files]}, str(out / "manifest.json"), root=root)
(out / ".graphify_python").write_text(sys.executable, encoding="utf-8")
(out / ".graphify_root").write_text(str(root), encoding="utf-8")
(out / ".graphify_extract.json").write_text(json.dumps(extraction), encoding="utf-8")
print(f"Graph: {graph.number_of_nodes()} nodes, {graph.number_of_edges()} edges.")
