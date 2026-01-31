#!/usr/bin/env python3
"""Creates final markdown files from template and component files, cleans up intermediate work files.

Usage: 50_assemble.py [options] <BASE_NAME> <OUTPUT_DIR>

Options:
  --summary-only     Create only summary file
  --transcript-only  Create only transcript file
  --comments-only    Create only comments file
  --summary-comments Create summary and comments files
  --debug            Keep intermediate work files

Default (no mode flag): Create summary, transcript, and comments files (Full mode)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from lib.assembler import Finalizer


def main() -> None:
    """CLI entry point."""
    debug = False
    mode = "full"
    args = []

    for arg in sys.argv[1:]:
        if arg == "--debug":
            debug = True
        elif arg == "--summary-only":
            mode = "summary-only"
        elif arg == "--transcript-only":
            mode = "transcript-only"
        elif arg == "--comments-only":
            mode = "comments-only"
        elif arg == "--summary-comments":
            mode = "summary-comments"
        else:
            args.append(arg)

    if len(args) < 1:
        print("ERROR: No BASE_NAME provided", file=sys.stderr)
        print(__doc__, file=sys.stderr)
        sys.exit(1)

    base_name = args[0]
    output_dir = Path(args[1]) if len(args) > 1 else Path(".")
    template_dir = Path(__file__).parent.parent / "templates"

    try:
        finalizer = Finalizer()

        if debug:
            print("Debug mode: keeping intermediate work files")

        if mode == "summary-only":
            finalizer.finalize_summary_only(base_name, output_dir, template_dir, debug)
        elif mode == "transcript-only":
            finalizer.finalize_transcript_only(base_name, output_dir, template_dir, debug)
        elif mode == "comments-only":
            finalizer.finalize_comments_only(base_name, output_dir, template_dir, debug)
        elif mode == "summary-comments":
            finalizer.finalize_summary_comments(base_name, output_dir, template_dir, debug)
        else:
            finalizer.finalize_full(base_name, output_dir, template_dir, debug)

    except Exception as e:
        print(f"ERROR: {str(e)}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
