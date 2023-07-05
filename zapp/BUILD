package(default_visibility = ["//visibility:public"])

load("@rules_python//python:defs.bzl",
     "py_library",
     "py_runtime",
     "py_runtime_pair"
)

load("zapp.bzl",
     "zapp_binary"
)

# The Python runtime we need
py_runtime(
    name = "python3_runtime",
    files = [],
    interpreter_path = "/usr/bin/python3",
    python_version = "PY3",
    visibility = ["//visibility:public"],
)

py_runtime_pair(
    name = "python_runtime",
    py2_runtime = None,
    py3_runtime = ":python3_runtime",
)

toolchain(
    name = "python3_toolchain",
    toolchain = ":python_runtime",
    toolchain_type = "@bazel_tools//tools/python:toolchain_type",
)


# Zapp plugins used as a runtime library by rules_zapp
py_library(
    name = "zapp_support",
    srcs = ["__init__.py"] + glob(["support/**/*.py"]),
    imports = [
        "..",
    ]
)


py_binary(
    name = "zappc",
    main = "compiler/__main__.py",
    srcs = glob(["support/**/*.py"]) + [
      "compiler/__main__.py"
    ],
    imports = [
        "..",
    ],
)

# Bootstrapping because we can
zapp_binary(
    name = "zappzappc",
    main = "compiler/__main__.py",
    srcs = glob(["support/**/*.py"]) + [
      "compiler/__main__.py"
    ],
    imports = [
        "..",
    ],
)
