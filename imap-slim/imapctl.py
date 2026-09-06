#!/usr/bin/env python3
"""Stateless command-line front-end for imap-slim.

Connects, does one thing, logs out, exits. There is deliberately no daemon: the
MCP server holds no connection until an action asks for one, so processes that
are merely enabled cost nothing, and at a few commands every few days a
short-lived connection beats one held open in the background. What the skill
saves is the tool schema an enabled MCP loads into every session whether it
touches mail or not.

Dispatch goes through actions.run_action, the same function the MCP tool calls,
so the two front-ends cannot drift apart.
"""

import argparse
import sys

import actions
from actions import MailAction

EXIT_OK = 0
EXIT_ERROR = 1
EXIT_USAGE = 2

# run_action returns rendered markdown, so failure is detected from the text it
# produced. Precise per-cause exit codes need structured results, which is a
# separate change; until then an action that failed is exit 1 and nothing finer
# is promised.
_FAILURE_PREFIXES = ("Error:", "**Connection", "**Login rejected", "# IMAP Stream - Setup Required")


def _add_account(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--account", help="account name for multi-account setups")


def build_parser() -> argparse.ArgumentParser:
    """Subcommands mirror the eleven actions one to one."""
    parser = argparse.ArgumentParser(
        prog="imap-slim-cli",
        description="Read, search and draft mail. Output is markdown, meant to be read.",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="print nothing; the exit code carries the outcome")
    parser.add_argument("-v", "--verbose", action="store_true", help="diagnostics on stderr")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")

    p = sub.add_parser("list", help="list messages in a folder")
    p.add_argument("folder")
    p.add_argument("--preview", action="store_true", help="include a body snippet per message")
    p.add_argument("--limit", type=int, default=20)
    _add_account(p)

    p = sub.add_parser("read", help="read one message")
    p.add_argument("folder")
    p.add_argument("message", help="MSG_ID, MSG_ID:N for a deeper quote level, or MSG_ID:full")
    _add_account(p)

    p = sub.add_parser("search", help="search a folder")
    p.add_argument("folder")
    p.add_argument("query")
    p.add_argument("--preview", action="store_true")
    p.add_argument("--limit", type=int, default=20)
    _add_account(p)

    p = sub.add_parser("draft", help="create or modify a draft")
    p.add_argument("--format", required=True, choices=["markdown", "plain"], help="required; there is no default")
    p.add_argument("--payload", required=True, help='JSON: {"to","subject","body"} or {"id","body"}')
    p.add_argument("--folder", help="required when modifying an existing draft, e.g. Drafts")
    _add_account(p)

    p = sub.add_parser("edit", help="replace text in a draft that has no HTML body")
    p.add_argument("folder")
    p.add_argument("--payload", required=True, help='JSON: {"id", "replacements":[{"old","new"}]}')
    _add_account(p)

    p = sub.add_parser("flag", help="add or remove flags")
    p.add_argument("folder")
    p.add_argument("payload", help="MSG_ID:+FLAG,-FLAG")
    _add_account(p)

    p = sub.add_parser("attachment", help="save an attachment to a temp file")
    p.add_argument("folder")
    p.add_argument("payload", help="MSG_ID:INDEX")
    _add_account(p)

    for name, helptext in [
        ("cleanup", "delete saved attachment temp files"),
        ("folders", "list folders"),
        ("accounts", "list configured accounts"),
    ]:
        p = sub.add_parser(name, help=helptext)
        _add_account(p)

    p = sub.add_parser("help", help="help on an action")
    p.add_argument("topic", nargs="?", default="overview")

    return parser


def to_action(args: argparse.Namespace) -> MailAction:
    """Turn parsed arguments into the same model the MCP tool receives.

    Raises:
        pydantic.ValidationError: if the arguments do not form a valid action.
    """
    fields: dict = {"action": args.command, "account": getattr(args, "account", None)}

    if args.command in {"list", "search"}:
        fields["folder"] = args.folder
        fields["limit"] = args.limit
        # The model requires an explicit choice; absence of the flag is False,
        # never "unspecified".
        fields["preview"] = bool(args.preview)
        if args.command == "search":
            fields["payload"] = args.query
    elif args.command == "read":
        fields["folder"] = args.folder
        fields["payload"] = args.message
    elif args.command == "draft":
        fields["format"] = args.format
        fields["payload"] = args.payload
        fields["folder"] = args.folder
    elif args.command in {"edit"}:
        fields["folder"] = args.folder
        fields["payload"] = args.payload
    elif args.command in {"flag", "attachment"}:
        fields["folder"] = args.folder
        fields["payload"] = args.payload
    elif args.command == "help":
        fields["payload"] = args.topic

    return MailAction(**{k: v for k, v in fields.items() if v is not None})


def main(argv: list[str] | None = None) -> int:
    """Run one command and return its exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help(sys.stderr)
        return EXIT_USAGE

    try:
        params = to_action(args)
    except Exception as exc:  # pydantic validation, or bad argument shapes
        print(f"Invalid arguments: {exc}", file=sys.stderr)
        return EXIT_USAGE

    if args.verbose:
        print(f"action={params.action} folder={params.folder} account={params.account or '(default)'}", file=sys.stderr)

    result = actions.run_action(params)
    failed = result.startswith(_FAILURE_PREFIXES)

    if not args.quiet:
        print(result, file=sys.stderr if failed else sys.stdout)

    return EXIT_ERROR if failed else EXIT_OK


if __name__ == "__main__":
    sys.exit(main())
