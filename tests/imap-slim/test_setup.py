"""setup.py's interactive flow.

It was never tested: an interactive script is awkward to drive, so it drifted
into a state where "update an account" meant retyping every field including the
password, and removing one existed only as a flag nobody would find.
"""

import importlib.util
from pathlib import Path
from unittest.mock import patch

import pytest

SETUP = Path(__file__).resolve().parent.parent.parent / "imap-slim" / "setup.py"


def load_setup():
    spec = importlib.util.spec_from_file_location("imap_setup", SETUP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def setup_mod(fake_keyring):
    """setup.py talks to keyring directly, so point it at the same fake store."""
    module = load_setup()
    module.keyring = fake_keyring
    import imap_client

    imap_client.keyring = fake_keyring
    return module


def seed(fake, name="work", server="mail.example.com", user="u@example.com", password="secret"):
    import json

    fake.set_password("imap-slim", "accounts", json.dumps([name]))
    fake.set_password("imap-slim", "default_account", name)
    fake.set_password("imap-slim", f"{name}:imap_server", server)
    fake.set_password("imap-slim", f"{name}:imap_port", "993")
    fake.set_password("imap-slim", f"{name}:imap_username", user)
    fake.set_password("imap-slim", f"{name}:imap_password", password)


class TestPromptShapes:
    """A current or suggested value is always shown in brackets.

    Readline pre-filling the edit buffer was tried and removed: it never
    rendered, so the prompt showed nothing after the colon and the user could
    not see what an empty answer would keep.
    """

    def test_a_default_is_shown_in_brackets_and_kept_on_enter(self, setup_mod):
        with patch("builtins.input", return_value="") as mock_input:
            assert setup_mod.ask("  Port", "993") == "993"
        assert mock_input.call_args.args[0] == "  Port [993]: "

    def test_the_account_name_is_offered_the_same_way(self, setup_mod):
        with patch("builtins.input", return_value="") as mock_input:
            assert setup_mod.ask("  Account name", "foo") == "foo"
        assert mock_input.call_args.args[0] == "  Account name [foo]: "

    def test_typing_replaces_the_default(self, setup_mod):
        with patch("builtins.input", return_value="143"):
            assert setup_mod.ask("  Port", "993") == "143"

    def test_no_default_means_a_plain_prompt(self, setup_mod):
        with patch("builtins.input", return_value="typed") as mock_input:
            assert setup_mod.ask("  Username (e.g., you@example.com)") == "typed"
        assert mock_input.call_args.args[0] == "  Username (e.g., you@example.com): "

    def test_the_hint_gives_way_to_the_current_value(self, setup_mod, fake_keyring):
        """A stored server is more useful than an example of one."""
        seed(fake_keyring)
        prompts = []

        def record(prompt):
            prompts.append(prompt)
            return ""

        with patch("builtins.input", side_effect=record), patch("getpass.getpass", return_value=""):
            setup_mod.collect_account_settings("work", existing=True)

        assert any(p == "  IMAP Server [mail.example.com]: " for p in prompts), prompts
        assert not any("e.g., mail.example.com" in p for p in prompts)


class TestUpdatingKeepsWhatYouDoNotRetype:
    def test_empty_password_keeps_the_stored_one(self, setup_mod, fake_keyring):
        seed(fake_keyring)

        with (
            patch.object(setup_mod, "ask", side_effect=["work", "mail.example.com", "993", "u@example.com"]),
            patch("getpass.getpass", return_value=""),
        ):
            setup_mod.add_account("work")

        assert fake_keyring.get_password("imap-slim", "work:imap_password") == "secret"

    def test_a_new_password_replaces_it(self, setup_mod, fake_keyring):
        seed(fake_keyring)

        with (
            patch.object(setup_mod, "ask", side_effect=["work", "mail.example.com", "993", "u@example.com"]),
            patch("getpass.getpass", return_value="fresh"),
        ):
            setup_mod.add_account("work")

        assert fake_keyring.get_password("imap-slim", "work:imap_password") == "fresh"

    def test_a_new_account_still_requires_a_password(self, setup_mod, fake_keyring):
        with (
            patch.object(setup_mod, "ask", side_effect=["mail.example.com", "993", "u@example.com"]),
            patch("getpass.getpass", return_value=""),
            pytest.raises(SystemExit),
        ):
            setup_mod.add_account("brand-new")


class TestRenaming:
    def test_renaming_moves_every_key_and_the_default(self, setup_mod, fake_keyring):
        seed(fake_keyring, name="work")

        setup_mod.rename_account("work", "office")

        assert fake_keyring.get_password("imap-slim", "office:imap_password") == "secret"
        assert fake_keyring.get_password("imap-slim", "office:imap_server") == "mail.example.com"
        assert fake_keyring.get_password("imap-slim", "work:imap_password") is None
        assert setup_mod.get_accounts() == ["office"]
        assert fake_keyring.get_password("imap-slim", "default_account") == "office"

    def test_updating_can_rename(self, setup_mod, fake_keyring):
        seed(fake_keyring, name="work")

        with (
            patch.object(setup_mod, "ask", side_effect=["office", "mail.example.com", "993", "u@example.com"]),
            patch("getpass.getpass", return_value=""),
        ):
            setup_mod.add_account("work")

        assert setup_mod.get_accounts() == ["office"]
        assert fake_keyring.get_password("imap-slim", "office:imap_password") == "secret"

    def test_renaming_onto_an_existing_account_is_refused(self, setup_mod, fake_keyring):
        import json

        seed(fake_keyring, name="work")
        fake_keyring.set_password("imap-slim", "accounts", json.dumps(["work", "office"]))

        with patch.object(setup_mod, "ask", return_value="office"), pytest.raises(SystemExit):
            setup_mod.add_account("work")

        assert fake_keyring.get_password("imap-slim", "work:imap_password") == "secret", "the source must survive"


class TestRemovingFromTheInteractiveMenu:
    def test_removal_asks_first_and_can_be_declined(self, setup_mod, fake_keyring):
        seed(fake_keyring, name="work")

        with patch("builtins.input", side_effect=["3", "n"]):
            setup_mod.interactive_setup()

        assert setup_mod.get_accounts() == ["work"], "declining must change nothing"

    def test_confirmed_removal_deletes_the_account(self, setup_mod, fake_keyring):
        seed(fake_keyring, name="work")

        with patch("builtins.input", side_effect=["3", "y"]):
            setup_mod.interactive_setup()

        assert setup_mod.get_accounts() == []
        assert fake_keyring.get_password("imap-slim", "work:imap_password") is None


class TestTheDefaultAccountIsVisible:
    """Which account is the default was only shown by --list, so every prompt
    offering a choice hid the consequence of picking none of them."""

    def seed_three(self, fake, default="vre.iki.fi"):
        import json

        fake.set_password("imap-slim", "accounts", json.dumps(["work", "vre.iki.fi", "gmail"]))
        fake.set_password("imap-slim", "default_account", default)

    def test_the_default_is_marked_in_a_listing(self, setup_mod, fake_keyring):
        self.seed_three(fake_keyring)
        assert setup_mod.account_names() == "work, vre.iki.fi (default), gmail"

    def test_no_accounts_reads_as_none(self, setup_mod, fake_keyring):
        assert setup_mod.account_names() == "(none)"

    def test_no_default_marks_nothing(self, setup_mod, fake_keyring):
        import json

        fake_keyring.set_password("imap-slim", "accounts", json.dumps(["work", "gmail"]))
        assert setup_mod.account_names() == "work, gmail"

    def test_the_interactive_menu_shows_it(self, setup_mod, fake_keyring, capsys):
        self.seed_three(fake_keyring)

        with patch("builtins.input", side_effect=["5"]):
            setup_mod.interactive_setup()

        assert "vre.iki.fi (default)" in capsys.readouterr().out

    def test_a_name_copied_with_its_marker_still_resolves(self, setup_mod):
        assert setup_mod.strip_default_marker("vre.iki.fi (default)") == "vre.iki.fi"
        assert setup_mod.strip_default_marker("  gmail  ") == "gmail"

    def test_choosing_a_marked_name_from_the_menu_works(self, setup_mod, fake_keyring):
        """Picking the default account for removal, pasted as displayed."""
        self.seed_three(fake_keyring, default="gmail")
        for suffix in ["imap_server", "imap_port", "imap_username", "imap_password"]:
            fake_keyring.set_password("imap-slim", f"gmail:{suffix}", "x")

        with patch("builtins.input", side_effect=["3", "gmail (default)", "y"]):
            setup_mod.interactive_setup()

        assert "gmail" not in setup_mod.get_accounts()
