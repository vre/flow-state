#!/usr/bin/env python3
"""IMAP Slim Setup - Configure IMAP credentials in system keychain.

This script manages IMAP account configurations, supporting multiple accounts.
Credentials are stored securely in the system keychain.

Usage:
    python setup.py                    # Interactive add/edit
    python setup.py --list             # List accounts
    python setup.py --add <name>       # Add named account
    python setup.py --remove <name>    # Remove account
    python setup.py --default <name>   # Set default account
    python setup.py --clear            # Remove all configuration
"""

import argparse
import getpass
import json
import sys

import keyring
from imap_client import SERVICE_NAME, _keyring_get


def ask(label: str, default: str = "") -> str:
    """Prompt for a value, showing any current one in brackets.

    `ask("  Port", "993")` renders `  Port [993]: ` and an empty answer keeps
    993. Readline pre-filling the edit buffer was tried and removed: the value
    never rendered, so the prompt showed nothing and the user could not see what
    they were about to keep.
    """
    if default:
        return input(f"{label} [{default}]: ").strip() or default
    return input(f"{label}: ").strip()


def account_names(accounts: list[str] | None = None) -> str:
    """Account names for a prompt, with the default one marked.

    Which account is the default was only visible from `--list`, so every other
    place that offered a choice between accounts left the consequence of picking
    none of them invisible.
    """
    accounts = get_accounts() if accounts is None else accounts
    if not accounts:
        return "(none)"
    default = _keyring_get("default_account")
    return ", ".join(f"{a} (default)" if a == default else a for a in accounts)


def strip_default_marker(name: str) -> str:
    """Accept a name copied straight out of a prompt that marked the default."""
    return name.removesuffix("(default)").strip()


def get_accounts() -> list[str]:
    """Get list of configured accounts."""
    accounts_json = _keyring_get("accounts")
    if accounts_json:
        return json.loads(accounts_json)
    return []


def save_accounts(accounts: list[str]):
    """Save accounts list to keychain."""
    keyring.set_password(SERVICE_NAME, "accounts", json.dumps(accounts))


def get_default_account() -> str | None:
    """Get default account name."""
    accounts = get_accounts()
    if not accounts:
        return None

    default = _keyring_get("default_account")
    if default and default in accounts:
        return default

    return accounts[0] if accounts else None


def set_default_account(name: str):
    """Set default account."""
    accounts = get_accounts()
    if name not in accounts:
        print(f"Error: Account '{name}' not found.")
        print(f"Available accounts: {account_names(accounts)}")
        sys.exit(1)

    keyring.set_password(SERVICE_NAME, "default_account", name)
    print(f"Default account set to: {name}")


def collect_account_settings(name: str, existing: bool = False) -> tuple[str, str, str, str | None]:
    """Interactively collect IMAP settings for an account.

    When the account exists, every field is pre-filled with its current value and
    can be edited in place. The password cannot be pre-filled - it is never read
    back - so an empty answer keeps the stored one.

    Returns:
        (server, port, username, password). password is None when the existing
        one is to be kept.
    """
    print(f"\nEnter IMAP settings for '{name}':")
    print()

    current_server = _keyring_get(f"{name}:imap_server") or "" if existing else ""
    current_port = _keyring_get(f"{name}:imap_port") or "993" if existing else ""
    current_user = _keyring_get(f"{name}:imap_username") or "" if existing else ""

    server = ask("  IMAP Server" if current_server else "  IMAP Server (e.g., mail.example.com)", current_server)
    if not server:
        print("Error: Server is required.")
        sys.exit(1)

    port = ask("  Port", current_port or "993") or "993"

    username = ask("  Username" if current_user else "  Username (e.g., you@example.com)", current_user)
    if not username:
        print("Error: Username is required.")
        sys.exit(1)

    print()
    if existing:
        password = getpass.getpass("  Password (hidden, Enter keeps the current one): ") or None
    else:
        password = getpass.getpass("  Password (hidden): ")
        if not password:
            print("Error: Password is required.")
            sys.exit(1)

    return server, port, username, password


def save_account_credentials(name: str, server: str, port: str, username: str, password: str):
    """Save account credentials to keychain."""
    accounts = get_accounts()

    keyring.set_password(SERVICE_NAME, f"{name}:imap_server", server)
    keyring.set_password(SERVICE_NAME, f"{name}:imap_port", port)
    keyring.set_password(SERVICE_NAME, f"{name}:imap_username", username)
    keyring.set_password(SERVICE_NAME, f"{name}:imap_password", password)

    if name not in accounts:
        accounts.append(name)
        save_accounts(accounts)


def rename_account(old: str, new: str):
    """Move an account's keys to a new name, keeping default and ordering.

    Copy everything, verify everything, and only then delete the originals. A
    delete that follows each individual copy leaves the account split across
    two names if any write in the middle fails, and the half under the old name
    is no longer reachable once the accounts list has moved on.
    """
    suffixes = ["imap_server", "imap_port", "imap_username", "imap_password"]

    copied = []
    for suffix in suffixes:
        value = _keyring_get(f"{old}:{suffix}")
        if value is None:
            continue
        keyring.set_password(SERVICE_NAME, f"{new}:{suffix}", value)
        copied.append((suffix, value))

    for suffix, value in copied:
        if _keyring_get(f"{new}:{suffix}") != value:
            print(
                f"Error: '{new}:{suffix}' could not be verified after copying. Account '{old}' is left untouched.",
                file=sys.stderr,
            )
            sys.exit(1)

    for suffix, _value in copied:
        try:
            keyring.delete_password(SERVICE_NAME, f"{old}:{suffix}")
        except keyring.errors.PasswordDeleteError:
            pass

    accounts = [new if a == old else a for a in get_accounts()]
    keyring.set_password(SERVICE_NAME, "accounts", json.dumps(accounts))
    if _keyring_get("default_account") == old:
        keyring.set_password(SERVICE_NAME, "default_account", new)
    print(f"Renamed account '{old}' to '{new}'.")


def add_account(name: str):
    """Add or update a named account."""
    accounts = get_accounts()
    existing = name in accounts

    if existing:
        print(f"Account '{name}' exists. Updating...")
        new_name = ask("  Account name", name)
        if new_name and new_name != name:
            if new_name in accounts:
                print(f"Error: account '{new_name}' already exists.")
                sys.exit(1)
            rename_account(name, new_name)
            name = new_name
    else:
        print(f"Adding new account: {name}")

    server, port, username, password = collect_account_settings(name, existing=existing)

    if password is None:
        password = _keyring_get(f"{name}:imap_password")
        if not password:
            print("Error: no stored password to keep. Enter one.")
            sys.exit(1)
        print("Keeping the stored password.")

    print("\nStoring credentials in keychain...")
    save_account_credentials(name, server, port, username, password)

    if len(get_accounts()) == 1:
        keyring.set_password(SERVICE_NAME, "default_account", name)
        print(f"Set '{name}' as default account.")

    print()
    print("=" * 50)
    print(f"  Account '{name}' configured!")
    print("=" * 50)
    print()
    print(f"  Server:   {server}:{port}")
    print(f"  Username: {username}")
    print("  Password: (stored in keychain)")
    print()


def remove_account(name: str):
    """Remove an account."""
    accounts = get_accounts()

    if name not in accounts:
        print(f"Error: Account '{name}' not found.")
        sys.exit(1)

    for key in ["imap_server", "imap_port", "imap_username", "imap_password"]:
        try:
            keyring.delete_password(SERVICE_NAME, f"{name}:{key}")
        except keyring.errors.PasswordDeleteError:
            pass

    accounts.remove(name)
    save_accounts(accounts)

    default = get_default_account()
    if default == name and accounts:
        keyring.set_password(SERVICE_NAME, "default_account", accounts[0])
        print(f"New default account: {accounts[0]}")

    print(f"Account '{name}' removed.")


def list_accounts():
    """List all configured accounts."""
    accounts = get_accounts()
    default = get_default_account()

    if not accounts:
        print("No accounts configured.")
        print("Run 'python setup.py' to add an account.")
        return

    print("Configured accounts:")
    for acc in accounts:
        marker = " (default)" if acc == default else ""
        username = _keyring_get(f"{acc}:imap_username")
        server = _keyring_get(f"{acc}:imap_server")
        print(f"  {acc}{marker}: {username} @ {server}")


def clear_all():
    """Remove all configuration."""
    accounts = get_accounts()

    print("Removing all stored credentials...")

    for acc in accounts:
        for key in ["imap_server", "imap_port", "imap_username", "imap_password"]:
            try:
                keyring.delete_password(SERVICE_NAME, f"{acc}:{key}")
            except keyring.errors.PasswordDeleteError:
                pass

    for key in ["accounts", "default_account"]:
        try:
            keyring.delete_password(SERVICE_NAME, key)
        except keyring.errors.PasswordDeleteError:
            pass

    print("All credentials removed.")


def interactive_setup():
    """Interactive setup - add or edit account."""
    print("=" * 50)
    print("  IMAP Slim Setup")
    print("=" * 50)
    print()
    print("This configures your IMAP connection.")
    print("Credentials are stored securely in system keychain.")
    print()

    accounts = get_accounts()

    if accounts:
        print(f"Existing accounts: {account_names(accounts)}")
        print()
        print("Options:")
        print("  1) Add new account")
        print("  2) Update existing account")
        print("  3) Remove an account")
        print("  4) Set the default account")
        print("  5) Cancel")
        print()
        choice = input("Choice [1]: ").strip() or "1"

        if choice == "5":
            print("Setup cancelled.")
            return

        if choice in {"3", "4"}:
            target = accounts[0] if len(accounts) == 1 else strip_default_marker(ask(f"Account ({account_names(accounts)})"))
            if target not in accounts:
                print(f"Error: Account '{target}' not found.")
                sys.exit(1)
            if choice == "3":
                confirm = input(f"Remove '{target}' and its stored password? [y/N]: ").strip().lower()
                if confirm != "y":
                    print("Cancelled.")
                    return
                remove_account(target)
            else:
                set_default_account(target)
            return

        if choice == "2":
            if len(accounts) == 1:
                name = accounts[0]
            else:
                name = strip_default_marker(input(f"Account to update ({account_names(accounts)}): "))
                if name not in accounts:
                    print(f"Error: Account '{name}' not found.")
                    sys.exit(1)
        else:
            name = input("Account name (e.g., work, personal): ").strip()
            if not name:
                print("Error: Account name is required.")
                sys.exit(1)
    else:
        name = input("Account name (e.g., work, personal) [default]: ").strip() or "default"

    add_account(name)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Configure IMAP credentials in system keychain",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python setup.py                    # Interactive setup
  python setup.py --list             # List accounts
  python setup.py --add work         # Add account named 'work'
  python setup.py --remove personal  # Remove 'personal' account
  python setup.py --default work     # Set 'work' as default
  python setup.py --clear            # Remove all configuration
""",
    )
    parser.add_argument("--list", action="store_true", help="List configured accounts")
    parser.add_argument("--add", metavar="NAME", help="Add or update named account")
    parser.add_argument("--remove", metavar="NAME", help="Remove named account")
    parser.add_argument("--default", metavar="NAME", help="Set default account")
    parser.add_argument("--clear", action="store_true", help="Remove all configuration")

    args = parser.parse_args()

    if args.list:
        list_accounts()
    elif args.add:
        add_account(args.add)
    elif args.remove:
        remove_account(args.remove)
    elif args.default:
        set_default_account(args.default)
    elif args.clear:
        clear_all()
    else:
        interactive_setup()


if __name__ == "__main__":
    main()
