#!/usr/bin/env python3
"""
Streammail Setup - Configure IMAP credentials in macOS Keychain.

This script interactively collects IMAP server settings and stores
them securely in the system keychain. The password is never logged
or displayed after entry.

Usage:
    python setup.py
"""

import getpass
import keyring
import sys

SERVICE_NAME = "streammail"


def setup():
    """Interactive setup for streammail IMAP configuration."""
    print("=" * 50)
    print("  Streammail Setup")
    print("=" * 50)
    print()
    print("This will configure your IMAP connection.")
    print("Credentials are stored securely in macOS Keychain.")
    print()

    # Check for existing config
    existing_server = keyring.get_password(SERVICE_NAME, "imap_server")
    if existing_server:
        print(f"Existing configuration found: {existing_server}")
        overwrite = input("Overwrite? [y/N]: ").strip().lower()
        if overwrite != 'y':
            print("Setup cancelled.")
            return
        print()

    # Collect IMAP settings
    print("Enter your IMAP server settings:")
    print()

    server = input("  IMAP Server (e.g., mail.example.com): ").strip()
    if not server:
        print("Error: Server is required.")
        sys.exit(1)

    port_input = input("  Port [993]: ").strip()
    port = port_input if port_input else "993"

    username = input("  Username (e.g., ville@example.com): ").strip()
    if not username:
        print("Error: Username is required.")
        sys.exit(1)

    print()
    password = getpass.getpass("  Password (hidden): ")
    if not password:
        print("Error: Password is required.")
        sys.exit(1)

    # Store in keychain
    print()
    print("Storing credentials in keychain...")

    try:
        keyring.set_password(SERVICE_NAME, "imap_server", server)
        keyring.set_password(SERVICE_NAME, "imap_port", port)
        keyring.set_password(SERVICE_NAME, "imap_username", username)
        keyring.set_password(SERVICE_NAME, "imap_password", password)

        print()
        print("=" * 50)
        print("  Setup complete!")
        print("=" * 50)
        print()
        print(f"  Server:   {server}:{port}")
        print(f"  Username: {username}")
        print(f"  Password: (stored in keychain)")
        print()
        print("You can now use streammail_mcp with Claude.")
        print()
        print("To test the connection:")
        print("  python -c \"from imap_client import test_connection; test_connection()\"")
        print()

    except Exception as e:
        print(f"Error storing credentials: {e}")
        sys.exit(1)


def show_config():
    """Display current configuration (without password)."""
    server = keyring.get_password(SERVICE_NAME, "imap_server")
    port = keyring.get_password(SERVICE_NAME, "imap_port")
    username = keyring.get_password(SERVICE_NAME, "imap_username")
    has_password = keyring.get_password(SERVICE_NAME, "imap_password") is not None

    if not server:
        print("No configuration found. Run 'python setup.py' to configure.")
        return

    print("Current streammail configuration:")
    print(f"  Server:   {server}:{port}")
    print(f"  Username: {username}")
    print(f"  Password: {'(set)' if has_password else '(not set)'}")


def clear_config():
    """Remove all stored credentials."""
    print("Removing stored credentials...")
    for key in ["imap_server", "imap_port", "imap_username", "imap_password"]:
        try:
            keyring.delete_password(SERVICE_NAME, key)
        except keyring.errors.PasswordDeleteError:
            pass
    print("Credentials removed.")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        if sys.argv[1] == "--show":
            show_config()
        elif sys.argv[1] == "--clear":
            clear_config()
        elif sys.argv[1] == "--help":
            print("Usage:")
            print("  python setup.py          Interactive setup")
            print("  python setup.py --show   Show current config")
            print("  python setup.py --clear  Remove stored credentials")
        else:
            print(f"Unknown option: {sys.argv[1]}")
            sys.exit(1)
    else:
        setup()
