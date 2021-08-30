import sys


def main():
    for e in sys.path:
        print(" -", e)

    print(f"hello, world! This is {__file__}")

    try:
        import yaml

        print("I have YAML! and nothing to do with it.", yaml.__file__)
    except ImportError:
        print("Don't have YAML.")

    exit(0)


if __name__ == "__main__":
    main()
