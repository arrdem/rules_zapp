load("@rules_zapp//zapp:zapp.bzl",
     "zapp_binary",
)

load("@rules_python//python:defs.bzl", "py_library")

load("@my_deps//:requirements.bzl",
     py_requirement="requirement",
)

zapp_binary(
    name = "hello_script",
    main = "hello.py",
    # entry_point is inferred from main =
)

zapp_binary(
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

zapp_binary(
    name = "hello_lib_deps",
    main = "hello.py",
    deps = [
        ":lib_hello",
    ],
)
