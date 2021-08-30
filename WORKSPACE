# WORKSPACE
#
# This file exists to configure the Bazel (https://bazel.build/) build tool to our needs.
# Particularly, it installs rule definitions and other capabilities which aren't in Bazel core.
# In the future we may have our own modifications to this config.

# Install the blessed Python and PyPi rule support
# From https://github.com/bazelbuild/rules_python

workspace(
    name = "rules_zapp",
)

load(
    "@bazel_tools//tools/build_defs/repo:git.bzl",
    "git_repository",
)

####################################################################################################
# Skylib
####################################################################################################
git_repository(
    name = "bazel_skylib",
    remote = "https://github.com/bazelbuild/bazel-skylib.git",
    tag = "1.0.3",
)
load("@bazel_skylib//:workspace.bzl", "bazel_skylib_workspace")
bazel_skylib_workspace()

git_repository(
    name = "rules_python",
    remote = "https://github.com/bazelbuild/rules_python.git",
    tag = "0.3.0",
)

register_toolchains(
    "//zapp:zappc_toolchain",
)
