"""
An implementation of driving zappc from Bazel.
"""


load("@bazel_skylib//lib:collections.bzl", "collections")
load("@rules_python//python:defs.bzl", "py_library", "py_binary")


DEFAULT_COMPILER = "@rules_zapp//zapp:zappc"
DEFAULT_RUNTIME  = "@rules_zapp//zapp:zapp_support"


def _store_path(path, ctx, imports):
    """Given a path, prepend the workspace name as the zappent directory"""

    # It feels like there should be an easier, less fragile way.
    if path.startswith("../"):
        # External workspace, for example
        # '../protobuf/python/google/protobuf/any_pb2.py'
        stored_path = path[len("../"):]

    elif path.startswith("external/"):
        # External workspace, for example
        # 'external/protobuf/python/__init__.py'
        stored_path = path[len("external/"):]

    else:
        # Main workspace, for example 'mypackage/main.py'
        stored_path = ctx.workspace_name + "/" + path

    matching_prefixes = []
    for i in imports:
        if stored_path.startswith(i):
            matching_prefixes.append(i)

    # Find the longest prefix match
    matching_prefixes = sorted(matching_prefixes, key=len, reverse=True)

    if matching_prefixes:
        # Strip the longest matching prefix
        stored_path = stored_path[len(matching_prefixes[0]):]

    # Strip any trailing /
    stored_path = stored_path.lstrip("/")

    return stored_path


def _check_script(point, sources_map):
    """Check that a given 'script' (eg. module:fn ref.) maps to a file in sources."""

    fname = point.split(":")[0].replace(".", "/") + ".py"
    if fname not in sources_map:
        fail("Point %s (%s) is not a known source!" % (fname, sources_map))


def _zapp_impl(ctx):
    """Implementation of zapp() rule"""

    # TODO: Take wheels and generate a .deps/ tree of them, filtering whl/pypi source files from srcs
    whls = []
    for lib in ctx.attr.wheels:
        for f in lib.data_runfiles.files.to_list():
            whls.append(f)

    # TODO: also handle ctx.attr.src.data_runfiles.symlinks
    srcs = [
        f for f in ctx.attr.src.default_runfiles.files.to_list()
        # Strip out transitive sources from PyPi archives
        if f.path.find("/pypi__") == -1
    ]

    # Find the list of directories to add to sys
    import_roots = collections.uniq([
        r for r in ctx.attr.src[PyInfo].imports.to_list()
    ] + [
        # The workspace root is implicitly an import root
        ctx.workspace_name
    ])

    # Dealing with main
    main_py_file = ctx.files.main
    main_py_ref = ctx.attr.entry_point
    if main_py_ref and main_py_file:
        fail("Only one of `main` or `entry_point` should be specified")
    elif main_py_ref:
        # Compute a main module
        main_py_file = main_py_ref.split(":")[0].replace(".", "/") + ".py"
    elif main_py_file:
        # Compute a main module reference
        if len(main_py_file) > 1:
            fail("Expected exactly one .py file, found these: %s" % main_py_file)
        main_py_file = main_py_file[0]
        if main_py_file not in ctx.attr.src.data_runfiles.files.to_list():
            fail("Main entry point [%s] not listed in srcs" % main_py_file, "main")

        # Compute the -m <> equivalent for the 'main' module
        main_py_ref = _store_path(main_py_file.path, ctx, import_roots).replace(".py", "").replace("/", ".")

    # Make a manifest of files to store in the .zapp file.  The
    # runfiles manifest is not quite right, so we make our own.
    sources_map = {}

    # Now add the regular (source and generated) files
    for input_file in srcs:
        stored_path = _store_path(input_file.short_path, ctx, import_roots)
        if stored_path:
            local_path = input_file.path
            if stored_path in sources_map and sources_map[stored_path] != '':
                fail("File path conflict between %s and %s" % sources_map[stored_path], local_path)

            sources_map[stored_path] = local_path

    _check_script(main_py_ref, sources_map)
    for p in ctx.attr.prelude_points:
        _check_script(p, sources_map)

    if "__main__.py" in sources_map:
        fail("__main__.py conflict:",
             sources_map["__main__.py"],
             "conflicts with required generated __main__.py")

    # Write the list to the manifest file
    manifest_file = ctx.actions.declare_file(ctx.label.name + ".zapp-manifest.json")
    ctx.actions.write(
        output = manifest_file,
        content = json.encode({
            "shebang": ctx.attr.shebang,
            "sources": sources_map,
            "zip_safe": ctx.attr.zip_safe,
            "prelude_points": ctx.attr.prelude_points,
            "entry_point": main_py_ref,
            "wheels": {w.path.split("/")[-1]: {"hashes": [], "source": w.path} for w in whls},
        }),
        is_executable = False,
    )

    # Run compiler
    ctx.actions.run(
        inputs = [
            manifest_file,
        ] + srcs + whls,
        tools = [],
        outputs = [ctx.outputs.executable],
        progress_message = "Building zapp file %s" % ctx.label,
        executable = ctx.executable.compiler,
        arguments = [
            "--debug",
            "-o", ctx.outputs.executable.path,
            manifest_file.path
        ],
        mnemonic = "PythonCompile",
        use_default_shell_env = True,
    )

    # .zapp file itself has no runfiles and no providers
    return []


zapp = rule(
    attrs = {
        "src": attr.label(mandatory = True),
        "main": attr.label(allow_single_file = True),
        "wheels": attr.label_list(),
        "entry_point": attr.string(),
        "prelude_points": attr.string_list(),
        "compiler": attr.label(
            default = Label(DEFAULT_COMPILER),
            executable = True,
            cfg = "host",
        ),
        "shebang": attr.string(default = "/usr/bin/env python3"),
        "zip_safe": attr.bool(default = True),
        "root_import": attr.bool(default = False),
    },
    executable = True,
    implementation = _zapp_impl,
)


def zapp_binary(name,
                main=None,
                entry_point=None,
                prelude_points=[],
                deps=[],
                imports=[],
                test=False,
                compiler=None,
                zip_safe=True,
                **kwargs):
    """A self-contained, single-file Python program, with a .zapp file extension.

    Args:
      Same as py_binary, but accepts some extra args -

      entry_point:
        The script to run as the main.

      prelude_points:
        Additional scripts (zapp middlware) to run before main.

      compiler:
        Lable identifying the zapp compiler to use. You shouldn't need to change this.

      zip_safe:
        Whether to import Python code and read datafiles directly from the zip
        archive. Otherwise, if False, all files are extracted to a temporary
        directory on disk each time the zapp file executes.
    """

    srcs = kwargs.pop("srcs", [])
    if main and main not in srcs:
        srcs.append(main)

    whls = []
    src_deps = []
    for d in deps:
        if d.find("//pypi__") != -1:
            whls.append(d + ":whl")
        else:
            src_deps.append(d)

    py_library(
        name = name + ".whls",
        data = whls,
    )

    py_library(
        name = name + ".lib",
        srcs = srcs,
        deps = (src_deps or []) + [DEFAULT_RUNTIME],
        imports = imports,
        **kwargs
    )

    zapp(
        name = name,
        src = name + ".lib",
        compiler = compiler,
        main = main,
        entry_point = entry_point,
        prelude_points = prelude_points,
        zip_safe = zip_safe,
        wheels = [name + ".whls"],
    )


def zapp_test(name, **kwargs):
    """Same as zapp_binary, just sets the test=True bit."""

    kwargs.pop("test")
    zapp_binary(name, test=True, **kwargs)
