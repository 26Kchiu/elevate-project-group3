package(default_visibility = ["//visibility:public"])

py_library(
    name = "knowledge",
    srcs = [
        "__init__.py",
        "curation_gate.py",
        "graph_service.py",
        "ingestion_pipeline.py",
    ],
    data = glob(["corpus/*", "ddl/*"]),
    deps = [
        "//enterprise/hr/agentic/hr_policy_agent/config",
    ],
)
