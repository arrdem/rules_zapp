package(default_visibility = ["//visibility:public"])

load("zapp.bzl",
     "zapp_binary",
     "zapp_toolchain"
)

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
    name = "bootstrap_zappc",
    main = "compiler/__main__.py",
    srcs = glob(["support/**/*.py"]) + [
      "compiler/__main__.py"
    ],
    imports = [
        "..",
    ],
)

toolchain_type(name = "toolchain_type")

zapp_toolchain(
    name = "zappc_info",
    compiler = ":bootstrap_zappc",
)

toolchain(
    name = "zappc_toolchain",
    toolchain = ":zappc_info",
    toolchain_type = ":toolchain_type",
)

# Now we can zapp zapp itself...
zapp_binary(
    name = "zappc",
    main = "compiler/__main__.py",
    srcs = glob(["support/**/*.py"]) + [
      "compiler/__main__.py"
    ],
    imports = [
        "..",
    ],
)
