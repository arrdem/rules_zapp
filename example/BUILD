load("@rules_zapp//zapp:zapp.bzl",
     "zapp_binary",
     "zapp_test",
)

load("@rules_python//python:defs.bzl",
     "py_library",
     "py_runtime_pair"
)

load("@my_deps//:requirements.bzl",
     py_requirement="requirement",
)

# Configuring a Python runtime

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

# Zapp examples & tests

py_test(
    name = "hello_native",
    main = "hello.py",
    srcs = ["hello.py"],
)

zapp_test(
    name = "hello_script",
    main = "hello.py",
    # entry_point is inferred from main =
)

zapp_test(
    name = "hello_deps",
    main = "hello.py",
    # deps also get zapped via their underlying wheels
    deps = [
        py_requirement("pyyaml"),
    ]
)

py_library(
    name = "lib_hello",
    srcs = [],
    deps = [
        py_requirement("pyyaml"),
    ]
)

zapp_test(
    name = "hello_lib_deps",
    main = "hello.py",
    deps = [
        ":lib_hello",
    ],
)


zapp_test(
    name = "hello_unzipped",
    zip_safe = False,
    main = "hello.py",
    deps = [
        ":lib_hello",
    ],
)
