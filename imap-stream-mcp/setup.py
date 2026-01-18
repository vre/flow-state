#!/usr/bin/env python3
"""
IMAP Stream Setup - Configure IMAP credentials in system keychain.

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
import keyring
import sys

SERVICE_NAME = "imap-stream"


def get_accounts() -> list[str]:
    """Get list of configured accounts."""
    accounts_json = keyring.get_password(SERVICE_NAME, "accounts")
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

    default = keyring.get_password(SERVICE_NAME, "default_account")
    if default and default in accounts:
        return default

    return accounts[0] if accounts else None


def set_default_account(name: str):
    """Set default account."""
    accounts = get_accounts()
    if name not in accounts:
        print(f"Error: Account '{name}' not found.")
        print(f"Available accounts: {', '.join(accounts) if accounts else '(none)'}")
        sys.exit(1)

    keyring.set_password(SERVICE_NAME, "default_account", name)
    print(f"Default account set to: {name}")


def collect_account_settings(name: str) -> tuple[str, str, str, str]:
    """Interactively collect IMAP settings for an account."""
    print(f"\nEnter IMAP settings for '{name}':")
    print()

    server = input("  IMAP Server (e.g., mail.example.com): ").strip()
    if not server:
        print("Error: Server is required.")
        sys.exit(1)

    port_input = input("  Port [993]: ").strip()
    port = port_input if port_input else "993"

    username = input("  Username (e.g., you@example.com): ").strip()
    if not username:
        print("Error: Username is required.")
        sys.exit(1)

    print()
    password = getpass.getpass("  Password (hidden): ")
    if not password:
        print("Error: Password is required.")
        sys.exit(1)

    return server, port, username, password


def save_account_credentials(name: str, server: str, port: str, username: str, password: str):
    """Save account credentials to keychain."""
    accounts = get_accounts()

    # Always use prefixed keys
    keyring.set_password(SERVICE_NAME, f"{name}:imap_server", server)
    keyring.set_password(SERVICE_NAME, f"{name}:imap_port", port)
    keyring.set_password(SERVICE_NAME, f"{name}:imap_username", username)
    keyring.set_password(SERVICE_NAME, f"{name}:imap_password", password)

    # Update accounts list
    if name not in accounts:
        accounts.append(name)
        save_accounts(accounts)


def add_account(name: str):
    """Add or update a named account."""
    accounts = get_accounts()

    if name in accounts:
        print(f"Account '{name}' exists. Updating...")
    else:
        print(f"Adding new account: {name}")

    server, port, username, password = collect_account_settings(name)

    print("\nStoring credentials in keychain...")
    save_account_credentials(name, server, port, username, password)

    # Set as default if first account
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
    print(f"  Password: (stored in keychain)")
    print()


def remove_account(name: str):
    """Remove an account."""
    accounts = get_accounts()

    if name not in accounts:
        print(f"Error: Account '{name}' not found.")
        sys.exit(1)

    # Remove credentials
    for key in ["imap_server", "imap_port", "imap_username", "imap_password"]:
        try:
            keyring.delete_password(SERVICE_NAME, f"{name}:{key}")
        except keyring.errors.PasswordDeleteError:
            pass

    # Update accounts list
    accounts.remove(name)
    save_accounts(accounts)

    # Update default if needed
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
        username = keyring.get_password(SERVICE_NAME, f"{acc}:imap_username")
        server = keyring.get_password(SERVICE_NAME, f"{acc}:imap_server")
        print(f"  {acc}{marker}: {username} @ {server}")


def clear_all():
    """Remove all configuration."""
    accounts = get_accounts()

    print("Removing all stored credentials...")

    # Remove all account credentials
    for acc in accounts:
        for key in ["imap_server", "imap_port", "imap_username", "imap_password"]:
            try:
                keyring.delete_password(SERVICE_NAME, f"{acc}:{key}")
            except keyring.errors.PasswordDeleteError:
                pass

    # Remove accounts list and default
    for key in ["accounts", "default_account"]:
        try:
            keyring.delete_password(SERVICE_NAME, key)
        except keyring.errors.PasswordDeleteError:
            pass

    print("All credentials removed.")


def interactive_setup():
    """Interactive setup - add or edit account."""
    print("=" * 50)
    print("  IMAP Stream Setup")
    print("=" * 50)
    print()
    print("This configures your IMAP connection.")
    print("Credentials are stored securely in system keychain.")
    print()

    accounts = get_accounts()

    if accounts:
        print(f"Existing accounts: {', '.join(accounts)}")
        print()
        print("Options:")
        print("  1) Add new account")
        print("  2) Update existing account")
        print("  3) Cancel")
        print()
        choice = input("Choice [1]: ").strip() or "1"

        if choice == "3":
            print("Setup cancelled.")
            return

        if choice == "2":
            if len(accounts) == 1:
                name = accounts[0]
            else:
                name = input(f"Account to update ({', '.join(accounts)}): ").strip()
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
"""
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
