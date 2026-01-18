# Development Notes

Internal notes for development. See also:
- `README.md` - User documentation
- `CLAUDE.md` - AI assistant context
- `CHANGELOG.md` - Version history

## Debug Commands

```bash
# Test MCP server
uv run python imap_stream_mcp.py

# Debug IMAP connection
uv run python debug_imap.py
uv run python debug_imap.py --debug  # Full protocol trace

# Run tests
uv run pytest tests/ -v
```

## Future Ideas

1. **Cache** - Folder listing/message caching
2. **Search operators** - Complex criteria (AND/OR)
3. **Flag management** - Mark as read/important

## Known Issues

None currently.

## References

- [Jesse Vincent's MCP philosophy](https://blog.fsck.com/2025/10/19/mcps-are-not-like-other-apis/)
- [StreamLinear example](https://blog.fsck.com/2025/12/27/streamlinear/)
