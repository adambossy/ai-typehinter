class SimpleIO:
    def read_text(self, path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not read {path}: {e}", file=sys.stderr)
            return None

    def tool_error(self, msg):
        print(f"Error: {msg}", file=sys.stderr)

    def tool_output(self, msg):
        print(f"Info: {msg}", file=sys.stderr)
