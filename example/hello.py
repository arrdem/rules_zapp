import sys


def main():
    for e in sys.path:
        print(" -", e)

    print("hello, world!")

    try:
        import yaml
        print("I have YAML! and nothing to do with it.", yaml.__file__)
    except ImportError:
        print("Don't have YAML.")


if __name__ == "__main__":
    main()
