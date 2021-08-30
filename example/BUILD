load("@rules_zapp//zapp:zapp.bzl",
     "zapp_binary",
     "zapp_test",
)

load("@rules_python//python:defs.bzl", "py_library")

load("@my_deps//:requirements.bzl",
     py_requirement="requirement",
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
