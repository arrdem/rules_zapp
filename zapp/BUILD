package(default_visibility = ["//visibility:public"])

load("zapp.bzl", "zapp_binary")

# Zapp plugins used as a runtime library by rules_zapp
py_library(
    name = "zapp_support",
    srcs = glob(["support/**/*.py"]),
    imports = [
        "..",
    ]
)

# Bootstrapping Zapp using py_binary
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

# For testing of zappc
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
