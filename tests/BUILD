package(default_visibility = ["//visibility:public"])

py_test(
    name = "test_policy_agent",
    srcs = ["test_policy_agent.py"],
    deps = ["//enterprise/hr/agentic/hr_policy_agent/agents"],
)

py_test(
    name = "test_hcm_agent",
    srcs = ["test_hcm_agent.py"],
    deps = [
        "//enterprise/hr/agentic/hr_policy_agent/agents",
        "//enterprise/hr/agentic/hr_policy_agent/security",
    ],
)

py_test(
    name = "test_itsm_agent",
    srcs = ["test_itsm_agent.py"],
    deps = [
        "//enterprise/hr/agentic/hr_policy_agent/agents",
        "//enterprise/hr/agentic/hr_policy_agent/security",
    ],
)

py_test(
    name = "test_supervisor_agent",
    srcs = ["test_supervisor_agent.py"],
    deps = ["//enterprise/hr/agentic/hr_policy_agent/agents"],
)

py_test(
    name = "test_confirmation_gate",
    srcs = ["test_confirmation_gate.py"],
    deps = ["//enterprise/hr/agentic/hr_policy_agent/security"],
)

py_test(
    name = "test_identity_injector",
    srcs = ["test_identity_injector.py"],
    deps = ["//enterprise/hr/agentic/hr_policy_agent/security"],
)

py_test(
    name = "test_guardrails",
    srcs = ["test_guardrails.py"],
    deps = ["//enterprise/hr/agentic/hr_policy_agent/security"],
)

py_test(
    name = "test_saga_orchestrator",
    srcs = ["test_saga_orchestrator.py"],
    deps = ["//enterprise/hr/agentic/hr_policy_agent/saga"],
)

py_test(
    name = "test_curation_gate",
    srcs = ["test_curation_gate.py"],
    deps = ["//enterprise/hr/agentic/hr_policy_agent/knowledge"],
)

py_test(
    name = "test_end_to_end",
    srcs = ["test_end_to_end.py"],
    deps = ["//enterprise/hr/agentic/hr_policy_agent/agents"],
)
