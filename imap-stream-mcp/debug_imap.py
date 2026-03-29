#!/usr/bin/env python3
"""Debug IMAP connection issues."""

import json
import socket
import ssl

import keyring

SERVICE_NAME = "imap-stream"


def get_credentials(account=None):
    """Get credentials from keychain.

    Args:
        account: Account name. None uses default account.
    """
    accounts_json = keyring.get_password(SERVICE_NAME, "accounts")
    if not accounts_json:
        return None, None, None, None

    accounts = json.loads(accounts_json)

    if account is None:
        account = keyring.get_password(SERVICE_NAME, "default_account") or accounts[0]

    if account not in accounts:
        print(f"ERROR: Account '{account}' not found. Available: {', '.join(accounts)}")
        return None, None, None, None

    server = keyring.get_password(SERVICE_NAME, f"{account}:imap_server")
    port = keyring.get_password(SERVICE_NAME, f"{account}:imap_port") or "993"
    username = keyring.get_password(SERVICE_NAME, f"{account}:imap_username")
    password = keyring.get_password(SERVICE_NAME, f"{account}:imap_password")

    return server, port, username, password


def debug_connection(account=None):
    """Test IMAP connection step by step."""
    # 1. Get credentials
    print("=" * 50)
    print("1. Checking stored credentials...")
    print("=" * 50)

    server, port, username, password = get_credentials(account)

    print(f"   Account: {account or '(default)'}")
    print(f"   Server:   {server}")
    print(f"   Port:     {port}")
    print(f"   Username: {username}")
    print(f"   Password: {'(set)' if password else '(not set)'}")
    print()

    if not all([server, username, password]):
        print("ERROR: Missing credentials. Run setup.py first.")
        return

    # 2. Test DNS resolution
    print("=" * 50)
    print("2. Testing DNS resolution...")
    print("=" * 50)
    try:
        ip = socket.gethostbyname(server)
        print(f"   ✓ {server} resolves to {ip}")
    except socket.gaierror as e:
        print(f"   ✗ DNS failed: {e}")
        return
    print()

    # 3. Test TCP connection
    print("=" * 50)
    print("3. Testing TCP connection...")
    print("=" * 50)
    try:
        sock = socket.create_connection((server, int(port)), timeout=10)
        print(f"   ✓ TCP connection to {server}:{port} OK")
        sock.close()
    except Exception as e:
        print(f"   ✗ TCP connection failed: {e}")
        return
    print()

    # 4. Test SSL/TLS
    print("=" * 50)
    print("4. Testing SSL/TLS handshake...")
    print("=" * 50)
    try:
        context = ssl.create_default_context()
        with socket.create_connection((server, int(port)), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname=server) as ssock:
                print(f"   ✓ SSL version: {ssock.version()}")
                print(f"   ✓ Cipher: {ssock.cipher()[0]}")
    except Exception as e:
        print(f"   ✗ SSL failed: {e}")
        return
    print()

    # 5. Test IMAP protocol
    print("=" * 50)
    print("5. Testing IMAP protocol...")
    print("=" * 50)
    try:
        import imaplib

        # Connect with debug
        imap = imaplib.IMAP4_SSL(server, int(port))
        print(f"   ✓ IMAP greeting: {imap.welcome.decode()[:80]}...")

        # Show capabilities
        typ, data = imap.capability()
        caps = data[0].decode() if data else "unknown"
        print(f"   ✓ Capabilities: {caps[:80]}...")
        print()

        # 6. Test authentication
        print("=" * 50)
        print("6. Testing authentication...")
        print("=" * 50)
        print(f"   Attempting LOGIN as '{username}'...")

        try:
            imap.login(username, password)
            print("   ✓ LOGIN successful!")

            # List some folders
            typ, folders = imap.list()
            print(f"   ✓ Found {len(folders)} folders")

            imap.logout()
            print()
            print("=" * 50)
            print("✓ ALL TESTS PASSED - Connection works!")
            print("=" * 50)

        except imaplib.IMAP4.error as e:
            print(f"   ✗ LOGIN failed: {e}")
            print()
            print("   Possible causes:")
            print("   - Wrong username (try full email address)")
            print("   - Wrong password")
            print("   - App password required (2FA)")
            print("   - Account locked")
            print()

            # Try to see if AUTHENTICATE methods are available
            if b"AUTH=PLAIN" in data[0]:
                print("   Server supports AUTH=PLAIN")
            if b"AUTH=LOGIN" in data[0]:
                print("   Server supports AUTH=LOGIN")

            imap.logout()

    except Exception as e:
        print(f"   ✗ IMAP error: {type(e).__name__}: {e}")
    print()


def test_with_imaplib_debug(account=None):
    """Test with full IMAP debug output."""
    import imaplib

    server, port, username, password = get_credentials(account)

    print("=" * 50)
    print("IMAP DEBUG MODE (full protocol trace)")
    print("=" * 50)
    print()

    # Enable debug
    imaplib.Debug = 4

    try:
        imap = imaplib.IMAP4_SSL(server, int(port))
        imap.login(username, password)
        print("\n✓ Success!")
        imap.logout()
    except Exception as e:
        print(f"\n✗ Failed: {e}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Debug IMAP connection issues")
    parser.add_argument("--account", help="Account name (default: use default account)")
    parser.add_argument("--debug", action="store_true", help="Full IMAP protocol trace")
    args = parser.parse_args()

    if args.debug:
        test_with_imaplib_debug(args.account)
    else:
        debug_connection(args.account)
        print("\nFor full protocol trace, run: python debug_imap.py --debug")
