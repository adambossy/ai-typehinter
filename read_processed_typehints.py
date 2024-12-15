import json
import sys


def process_first_ten_untyped_seqs(json_file):
    with open(json_file) as f:
        data = json.load(f)

    count = 0
    # Iterate through repos
    for repo in data:
        # Iterate through source files
        for src_file in data[repo]["src_files"]:
            if count >= 10:
                return

            untyped_seq = data[repo]["src_files"][src_file]["untyped_seq"]
            formatted_seq = untyped_seq.replace("[EOL]", "\n")

            print(f"\n=== File {count + 1}: {src_file} ===\n")
            print(formatted_seq)
            print("\n" + "=" * 80 + "\n")

            count += 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python read_processed_typehints.py <json_file>")
        sys.exit(1)

    process_first_ten_untyped_seqs(sys.argv[1])
