"""Tests for builder-mcp generators."""

from __future__ import annotations

import json

from conftest import load_builder_mcp_script

generate_mcp = load_builder_mcp_script("generate_mcp")
generate_packaging = load_builder_mcp_script("generate_packaging")
generate_pyproject = load_builder_mcp_script("generate_pyproject")


class TestGenerateServer:
    def test_defaults_to_stdio_transport(self):
        code = generate_mcp.generate_server({"domain": "test", "actions": ["list"]})

        assert 'mcp = FastMCP("test_mcp")' in code
        assert 'FastMCP("test_mcp", instructions=' not in code
        assert "mcp.run()" in code
        assert 'mcp.run(transport="streamable-http")' not in code

    def test_adds_streamable_http_transport(self):
        code = generate_mcp.generate_server(
            {
                "domain": "test",
                "actions": ["list"],
                "transport": "streamable-http",
            }
        )

        assert 'mcp.run(transport="streamable-http")' in code

    def test_adds_server_instructions(self):
        code = generate_mcp.generate_server(
            {
                "domain": "test",
                "actions": ["list"],
                "instructions": "Use for test data",
            }
        )

        assert 'mcp = FastMCP("test_mcp", instructions="Use for test data")' in code


class TestGeneratePyproject:
    def test_http_transport_adds_uvicorn(self):
        text = generate_pyproject.generate_pyproject(
            {
                "domain": "test",
                "transport": "streamable-http",
            }
        )

        assert '"uvicorn>=0.30.0"' in text

    def test_stdio_transport_does_not_add_uvicorn(self):
        text = generate_pyproject.generate_pyproject({"domain": "test"})

        assert '"uvicorn>=0.30.0"' not in text


class TestGeneratePackaging:
    def test_stdio_mcp_json_uses_command_transport(self):
        config = json.loads(generate_packaging.generate_mcp_json("test"))

        assert config["test-mcp"]["command"] == "uv"
        assert "args" in config["test-mcp"]
        assert "type" not in config["test-mcp"]

    def test_http_mcp_json_uses_url_transport(self):
        config = json.loads(
            generate_packaging.generate_mcp_json(
                "test",
                transport="streamable-http",
            )
        )

        assert config["test-mcp"]["type"] == "http"
        assert config["test-mcp"]["url"] == "http://localhost:${PORT}/mcp"
        assert "command" not in config["test-mcp"]

    def test_http_readme_mentions_remote_install(self):
        readme = generate_packaging.generate_readme(
            "test",
            "Test operations",
            ["list"],
            transport="streamable-http",
        )

        assert '"type": "http"' in readme
        assert "http://localhost:${PORT}/mcp" in readme
        assert "uv run test-mcp" in readme
