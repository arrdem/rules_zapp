load("@rules_zapp//zapp:zapp.bzl",
     "zapp_binary",
)

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
