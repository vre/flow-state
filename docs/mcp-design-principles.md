# MCP Design Principles for LLM Consumption

LLM APIs differ fundamentally from traditional APIs. This document describes design principles that work when the consumer is a language model.

## Background: Why Traditional API Principles Fail

### Token Economics

An LLM's context window is a finite resource. Every tool consumes tokens at two stages:

1. **Startup**: Tool descriptions are loaded into context
2. **Usage**: Responses consume context

Jesse Vincent analyzed Microsoft's Playwright MCP:
- 21 tools
- 13,678 tokens at startup
- ~7% of Claude's context window *before anything is done*

Each tool brings:
- Function name and description
- Parameter names, types, descriptions
- Examples (if any)

10 tools × 500 tokens/tool = 5,000 tokens. 50 tools = 25,000 tokens. Context exhausted.

### Response Size

Playwright MCP's navigation returned 25,837 tokens - exceeding Claude's 25,000 token tool limit. Result: cascade failure, entire operation failed.

Traditional APIs return all data. LLM APIs must return *exactly what's needed*.

### Fail-fast vs. Recovery

Traditional API design:
```
Invalid input → HTTP 400 → Developer reads docs → Fixes
```

An LLM doesn't re-read documentation mid-operation. It needs:
```
Invalid input → Explanation of what went wrong → Suggestion how to fix → LLM fixes
```

## Core Principles

### 1. Single Tool + Action Dispatcher

Don't create N endpoints. Create one tool that routes based on action.

```
❌ Traditional            ✅ LLM-friendly
─────────────────────────────────────────────
list_messages()           use_mail(action="list")
read_message()            use_mail(action="read")
search_messages()         use_mail(action="search")
create_draft()            use_mail(action="draft")
```

**Token savings**: 4 tools × ~400 tokens = 1,600 tokens → 1 tool × ~200 tokens.

**Cognitive savings**: LLM doesn't choose between 4 tools, only an action.

### 2. Help Action - Progressive Documentation

The tool documents itself. `help` action returns usage instructions *when needed*.

```python
use_mail(action="help")                        # overview
use_mail(action="help", payload="search")      # search action details
use_mail(action="help", payload="query_syntax") # query syntax explanation
```

**Benefit**: Documentation doesn't consume context at startup. LLM requests more info when needed.

This is the "string to pull" model: LLM gets minimal instructions first, then more when required.

### 3. Postel's Law in Practice

> "Be liberal in what you accept, strict in what you produce."

**Liberal in inputs**:

```python
# All of these work - parser normalizes:
use_mail(action="search", payload="from:boss@example.com")
use_mail(action="search", payload="boss@example.com last week")
use_mail(action="search", payload="FROM:BOSS@EXAMPLE.COM")  # case-insensitive
use_mail(action="search", folder="INBOX", payload="from:boss")
```

Vincent: "Accepting both CSS and XPath selectors dramatically improved performance."

Same principle: if the LLM can reasonably express intent, accept it.

**Strict in outputs**:

Response structure is always the same:
```json
{
  "messages": [...],
  "count": 5,
  "has_more": true
}
```

LLM can rely on structure for downstream processing.

### 4. Payload vs Named Parameters

| Type | Use Case | Example |
|------|----------|---------|
| `payload` | Free-form, identifier, human input | `"from:boss project:alpha"` |
| Named | Structural, validatable, control parameters | `limit=20`, `folder="INBOX"` |

**In practice**:
```python
def use_mail(
    action: str,           # required, drives logic
    payload: str = None,   # free-form content
    folder: str = None,    # structural, validatable
    limit: int = 20        # control parameter
)
```

**Rule**: Support both ways to express the same thing. Don't force LLM to remember exact syntax.

### 5. Error Messages Guide

```
❌ Traditional
"Error: Invalid message ID"
"Error 404: Not found"

✅ LLM-friendly
"Message 12345 not found in INBOX.
 Folder contains 847 messages, newest ID is 98234.
 Try: {action: 'list', folder: 'INBOX'} to see recent messages."

"Unknown search syntax: 'last week'
 Supported date formats: since:YYYY-MM-DD, before:YYYY-MM-DD
 Try: {action: 'search', payload: 'since:2025-01-21'}"
```

Error message includes:
1. What was attempted
2. Why it failed
3. Concrete example how to fix

## Atomic vs Compound: What Goes in Code, What Goes to LLM

This is the central design decision.

### Atomic Model

```
LLM: orders(action="delayed", payload="warehouse:EU-WEST")
     → [ORD-4401, ORD-4405, ORD-4420]
LLM: orders(action="get", payload="ORD-4401")
     → {customer: "Acme Corp", items: 3, ship_by: "2025-02-01"}
LLM: inventory(action="check", payload="SKU-900 warehouse:EU-WEST")
     → {available: 12, reserved: 3, restock_eta: "2025-02-03"}
```

**LLM glues** calls together. Flexible, but:
- More roundtrips
- Each call can fail
- LLM can make mistakes in the chain

### Compound Model

```
LLM: orders(action="fulfillment_risk", payload="EU-WEST 2025-02-01..02-03")
     → [{order: "ORD-4401", customer: "Acme Corp", risk: "low_stock",
         items: [{sku: "SKU-900", available: 12, needed: 15,
                  restock_eta: "2025-02-03"}]}]
```

**Code glues** internally. Faster, more reliable, but:
- Less flexible
- Must know in advance what combinations are needed

### When to Use Which?

**Move to code when**:
- Same chain repeats often
- Chain requires >3 calls
- Error in chain is critical

**Leave to LLM when**:
- Rare combination
- Exploratory use
- You don't yet know what's needed

**Development cycle**:
1. Start atomic
2. Log what chains LLM makes
3. When you see repeating chains → combine in code
4. Iterate

## Development Cycle: Log, Learn, Iterate

### Log Unrecognized Queries

```python
def parse_payload(payload: str):
    try:
        return parse(payload)
    except UnknownPattern:
        logger.info(f"Unsupported query pattern: {payload}")
        return suggest_alternatives(payload)
```

The log tells you what users (and LLM) are trying. From it you see:
- What syntax to support
- What chains to combine
- Where documentation is unclear

### From Use Cases to API

1. Write use cases in natural language
2. Think how LLM would solve them with current tools
3. Identify repeating chains
4. Build those into code

Example:
```
Use case: "Orders at risk of missing ship-by date due to low stock"

Atomic solution:
1. orders(action="delayed") → orders
2. for each: orders(action="get") → order details
3. for each: inventory(action="check") → stock levels
4. filter: available < needed AND restock_eta > ship_by

Compound solution:
orders(action="fulfillment_risk", payload="EU-WEST") → all at once
```

If this is a common query, compound is better.

## Anti-patterns

### ❌ Too Many Tools

```python
# Bad: 17 tools, each consuming context
getOrders(), getOrderStatus(), getOrderHistory(), getShipmentRoutes(),
getCustomers(), getCustomerPreferences(), getCustomerHistory(),
getInventory(), getInventoryLevels(), getInventoryForecasts(),
getWarehouses(), getWarehouseCapacity(), getWarehouseHistory(),
getSuppliers(), getCarriers(), getDeliverySlots(), getAlerts()
```

**Fix**: Group by domain: `orders()`, `customers()`, `inventory()`, `warehouses()`, `logistics()`

**Note**: Claude Code now supports deferred tool loading — tools can be discoverable without consuming context tokens at startup (85% reduction measured). This mitigates the token cost of many tools, but the cognitive cost (model confusion in tool selection) remains. Grouping by domain is still the primary fix.

### ❌ Strict Validation Without Guidance

```python
# Bad
if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
    raise ValueError("Invalid date format")

# Better
if not re.match(r'^\d{4}-\d{2}-\d{2}$', date):
    parsed = fuzzy_parse_date(date)  # try to interpret
    if parsed:
        return parsed
    raise ValueError(
        f"Could not parse date '{date}'. "
        f"Try format YYYY-MM-DD, e.g., '2025-01-28'"
    )
```

### ❌ Response Too Large

```python
# Bad: return all data
def get_order(order_id):
    return {
        "order": {...},            # basic info
        "items": [...],            # 50 line items
        "customer": {...},         # full customer profile
        "shipments": [...],        # shipping history
        "payments": [...],         # payment history
        "audit_log": [...],        # change history
    }

# Better: return what was requested
def orders(action, payload):
    if action == "get":
        return {"order": basic_info}
    if action == "get" and "items" in payload:
        return {"order": basic_info, "items": [...]}
```

### ❌ Documentation Only at Startup

```python
# Bad: long docstring loaded every time
def use_mail(action, payload):
    """
    Email operations tool.

    Actions:
    - list: Lists messages in folder...
      Parameters: folder (required), limit (optional, default 20)...
      Examples: ...
    - read: Reads a message...
    [100 lines of documentation]
    """

# Better: minimal docstring + help action
def use_mail(action, payload):
    """Email operations. Actions: list|read|search|draft|help"""
    if action == "help":
        return get_documentation(payload)  # payload = topic
```

### ❌ Unclear Names

```python
# Bad
def process(data): ...
def handle(item): ...
def do_thing(x, y): ...

# Better
def use_mail(action, payload): ...
def orders(action, payload): ...
def inventory(action, payload): ...
```

Vincent: "Names matter enormously. Clear, descriptive method names guide LLMs more effectively than strict type validation."

### ❌ Assuming LLM Remembers Context

```python
# Bad: assuming LLM uses same folder value
list_messages()  # returns INBOX
read_message(id=123)  # from which folder? LLM forgot

# Better: each call is self-contained
use_mail(action="list", folder="INBOX")
use_mail(action="read", folder="INBOX", payload="123")
```

### ❌ Fail-fast Without Recovery Path

```python
# Bad
if error:
    raise Exception("Failed")

# Better
if error:
    return {
        "error": "Message not found",
        "suggestion": "Try listing messages first",
        "example": {"action": "list", "folder": folder}
    }
```

## Example: imap-stream-mcp

```python
def use_mail(
    action: str,           # list|read|search|draft|flag|folders|accounts|help
    folder: str = None,    # INBOX, Sent, etc.
    payload: str = None,   # action-specific: msg_id, search query, draft JSON
    limit: int = 20        # max results
)
```

**One tool**, 8 actions, ~200 tokens at startup.

Search syntax is flexible:
- `from:address` - sender
- `subject:text` - subject
- `since:YYYY-MM-DD` - after date
- Free text - searches subject and body

Error messages guide:
```
"Folder 'Inbx' not found. Available folders: INBOX, Sent, Drafts, Trash.
 Try: {action: 'folders'} to see all folders."
```

## Summary

| Traditional API | LLM API |
|-----------------|---------|
| Many endpoints | One tool + action |
| Documentation separate | `help` action |
| Strict validation | Flexible input, parser normalizes |
| Fail-fast | Suggest correction |
| Return everything | Return what's needed |
| Type checking | Clear names guide usage |

**Core insight**: An LLM is a skilled but fallible worker. Design for human-like problem-solving, not machine precision.

## References

- Jesse Vincent: [MCPs Are Not Like Other APIs](https://blog.fsck.com/2025/10/19/mcps-are-not-like-other-apis/) (2025)
- Postel's Law: RFC 793 (1981)
