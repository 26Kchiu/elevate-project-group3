package(default_visibility = ["//visibility:public"])

py_library(
    name = "eval",
    srcs = [
        "__init__.py",
        "eval_runner.py",
    ],
    data = ["evalset.json"],
    deps = [
        "//enterprise/hr/agentic/hr_policy_agent/agents",
        "//enterprise/hr/agentic/hr_policy_agent/knowledge",
    ],
)
