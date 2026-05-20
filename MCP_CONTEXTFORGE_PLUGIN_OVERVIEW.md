# MCP Context Forge: Plugin-Powered AI Gateway

## Overview

**ContextForge** is an open source registry and proxy that federates MCP (Model Context Protocol), A2A (Agent-to-Agent), and REST/gRPC APIs with centralized governance, discovery, and observability. At its core, ContextForge provides a **production-ready plugin framework** that enables extensible AI safety middleware, content security, policy enforcement, and operational excellence.

### What is ContextForge?

ContextForge acts as a unified gateway layer for AI infrastructure, providing:

- **Tools Gateway** — MCP, REST, gRPC-to-MCP translation, and TOON compression
- **Agent Gateway** — A2A protocol, OpenAI-compatible and Anthropic agent routing
- **API Gateway** — Rate limiting, auth, retries, and reverse proxy for REST services
- **Plugin Extensibility** — 40+ built-in plugins for transports, protocols, and integrations
- **Observability** — OpenTelemetry tracing with Phoenix, Jaeger, Zipkin, and other OTLP backends

It runs as a fully compliant MCP server, deployable via PyPI or Docker, and scales to multi-cluster environments on Kubernetes with Redis-backed federation and caching.

---

## Plugin Framework: The Heart of ContextForge

The plugin framework is what makes ContextForge truly extensible and production-ready. It provides a powerful system for intercepting and transforming requests and responses at various points in the gateway lifecycle.

### Why Plugins Matter

Plugins enable you to:

- **Enforce AI Safety** — Block harmful content, detect PII, apply content moderation
- **Implement Security Policies** — Custom authentication, authorization, and access control
- **Transform Data** — Normalize inputs, filter outputs, mask sensitive information
- **Integrate External Services** — Connect to LlamaGuard, OpenAI Moderation, custom safety APIs
- **Monitor and Audit** — Log requests, track usage, generate compliance reports
- **Optimize Performance** — Cache responses, compress data, batch requests

### Plugin Architecture

ContextForge supports two types of plugins:

#### 1. Self-Contained Plugins (Native Python)
- Written in Python and run directly in the gateway process
- **Sub-millisecond latency** (<1ms)
- Perfect for high-frequency operations like PII filtering and regex transformations
- Examples: `pii_filter`, `regex_filter`, `deny_filter`, `resource_filter`

#### 2. External Service Plugins (MCP-based)
- Call external AI safety services via HTTP/MCP
- Support microservice integrations with authentication
- 10-100ms latency depending on service
- Examples: LlamaGuard, OpenAI Moderation, custom safety services

---

## Plugin Lifecycle Hooks

Plugins can implement hooks at these critical lifecycle points:

### HTTP Authentication & Middleware Hooks

| Hook | Description | Use Cases |
|------|-------------|-----------|
| `http_pre_request` | Before any authentication (middleware) | Header transformation, correlation IDs |
| `http_auth_resolve_user` | Custom user authentication (auth layer) | LDAP, mTLS, token auth, external auth services |
| `http_auth_check_permission` | Custom permission checking (RBAC layer) | Bypass RBAC, time-based access, IP restrictions |
| `http_post_request` | After request completion (middleware) | Audit logging, metrics, response headers |

### MCP Protocol Hooks

| Hook | Description | Use Cases |
|------|-------------|-----------|
| `prompt_pre_fetch` | Before prompt template retrieval | Input validation, access control |
| `prompt_post_fetch` | After prompt template retrieval | Content filtering, transformation |
| `tool_pre_invoke` | Before tool execution | Parameter validation, safety checks |
| `tool_post_invoke` | After tool execution | Result filtering, audit logging |
| `resource_pre_fetch` | Before resource retrieval | Protocol/domain validation |
| `resource_post_fetch` | After resource retrieval | Content scanning, size limits |
| `agent_pre_invoke` | Before agent invocation | Message filtering, access control |
| `agent_post_invoke` | After agent response | Response filtering, audit logging |

---

## Built-in Plugins (40+ Available)

ContextForge ships with a comprehensive set of production-ready plugins:

### Security & Compliance

#### PII Filter Plugin
Detects and masks Personally Identifiable Information:
- Social Security Numbers (SSN)
- Credit card numbers
- Email addresses
- Phone numbers
- AWS access keys
- Multiple masking strategies: redact, partial, hash, tokenize

```yaml
- name: "PIIFilterPlugin"
  kind: "plugins.pii_filter.pii_filter.PIIFilterPlugin"
  hooks: ["prompt_pre_fetch", "tool_pre_invoke"]
  mode: "enforce"
  priority: 50
  config:
    detect_ssn: true
    detect_credit_card: true
    detect_email: true
    detect_phone: true
    detect_aws_keys: true
    default_mask_strategy: "partial"
    block_on_detection: false
```

#### Deny List Plugin
Block requests containing specific terms or patterns:

```yaml
- name: "DenyListPlugin"
  kind: "plugins.deny_filter.deny.DenyListPlugin"
  hooks: ["prompt_pre_fetch"]
  mode: "enforce"
  priority: 10
  config:
    words:
      - "blocked_term"
      - "inappropriate_content"
```

### Content Transformation

#### Regex Filter Plugin
Find and replace text patterns with powerful regex support:

```yaml
- name: "ReplaceBadWordsPlugin"
  kind: "plugins.regex_filter.search_replace.SearchReplacePlugin"
  hooks: ["prompt_pre_fetch", "tool_post_invoke"]
  mode: "enforce"
  priority: 100
  config:
    words:
      - search: "password\\s*[:=]\\s*\\S+"
        replace: "password: [REDACTED]"
```

#### Resource Filter Plugin
Validate and filter resource requests:

```yaml
- name: "ResourceFilterExample"
  kind: "plugins.resource_filter.resource_filter.ResourceFilterPlugin"
  hooks: ["resource_pre_fetch", "resource_post_fetch"]
  mode: "enforce"
  priority: 50
  config:
    max_content_size: 1048576  # 1MB
    allowed_protocols: ["http", "https"]
    blocked_domains: ["malicious.example.com"]
    content_filters:
      - pattern: "password\\s*[:=]\\s*\\S+"
        replacement: "password: [REDACTED]"
```

---

## Plugin Configuration

### Quick Start

1. **Enable plugins** in `.env`:
```bash
PLUGINS_ENABLED=true
PLUGINS_CONFIG_FILE=plugins/config.yaml
```

2. **Configure plugins** in `plugins/config.yaml`:
```yaml
plugins:
  - name: "PIIFilterPlugin"
    kind: "plugins.pii_filter.pii_filter.PIIFilterPlugin"
    description: "Detects and masks Personally Identifiable Information"
    version: "0.1.0"
    author: "Your Name"
    hooks: ["prompt_pre_fetch", "tool_pre_invoke"]
    tags: ["security", "pii", "compliance"]
    mode: "enforce"
    priority: 50
    conditions:
      - prompts: []     # Empty = apply to all prompts
        server_ids: []  # Apply to specific servers
        tenant_ids: []  # Apply to specific tenants
    config:
      detect_ssn: true
      detect_email: true
      default_mask_strategy: "partial"

# Global settings
plugin_settings:
  parallel_execution_within_band: true
  plugin_timeout: 30
  fail_on_plugin_error: false
  plugin_health_check_interval: 60
```

3. **Restart the gateway**:
```bash
make dev
```

### Plugin Modes

- **`enforce`**: Blocks violations and prevents request processing
- **`permissive`**: Logs violations but allows request to continue
- **`disabled`**: Plugin is not executed (useful for temporary disabling)

### Plugin Priority

Lower priority numbers run first (higher priority). Recommended ranges:
- **1-50**: Critical security plugins (PII, access control)
- **51-100**: Content filtering and validation
- **101-200**: Transformations and enhancements
- **201+**: Logging and monitoring

---

## Writing Custom Plugins

### Three Hook Registration Patterns

#### Pattern 1: Convention-Based (Recommended)

The simplest approach — just name your method to match the hook type:

```python
from mcpgateway.plugins.framework import (
    Plugin,
    PluginContext,
    ToolPreInvokePayload,
    ToolPreInvokeResult,
)

class MyPlugin(Plugin):
    """Convention-based hook - method name matches hook type."""

    async def tool_pre_invoke(
        self,
        payload: ToolPreInvokePayload,
        context: PluginContext
    ) -> ToolPreInvokeResult:
        """This hook is automatically discovered by its name."""

        # Your logic here
        modified_args = {**payload.args, "processed": True}

        modified_payload = ToolPreInvokePayload(
            name=payload.name,
            args=modified_args,
            headers=payload.headers
        )

        return ToolPreInvokeResult(
            modified_payload=modified_payload,
            metadata={"processed_by": self.name}
        )
```

#### Pattern 2: Decorator-Based (Custom Method Names)

Use the `@hook` decorator to register a hook with a custom method name:

```python
from mcpgateway.plugins.framework import Plugin, PluginContext
from mcpgateway.plugins.framework.decorator import hook
from mcpgateway.plugins.framework import (
    ToolHookType,
    ToolPostInvokePayload,
    ToolPostInvokeResult,
)

class MyPlugin(Plugin):
    """Decorator-based hook with custom method name."""

    @hook(ToolHookType.TOOL_POST_INVOKE)
    async def my_custom_handler_name(
        self,
        payload: ToolPostInvokePayload,
        context: PluginContext
    ) -> ToolPostInvokeResult:
        """Method name doesn't match hook type, but @hook decorator registers it."""

        # Your logic here
        return ToolPostInvokeResult(continue_processing=True)
```

#### Pattern 3: Custom Hooks (Advanced)

Register completely new hook types with custom payload and result types:

```python
from mcpgateway.plugins.framework import Plugin, PluginContext, PluginPayload, PluginResult
from mcpgateway.plugins.framework.decorator import hook

# Define custom payload type
class EmailPayload(PluginPayload):
    recipient: str
    subject: str
    body: str

# Define custom result type
class EmailResult(PluginResult[EmailPayload]):
    pass

class MyPlugin(Plugin):
    """Custom hook with new hook type."""

    @hook("email_pre_send", EmailPayload, EmailResult)
    async def validate_email(
        self,
        payload: EmailPayload,
        context: PluginContext
    ) -> EmailResult:
        """Completely new hook type: 'email_pre_send'"""

        # Validate email address
        if "@" not in payload.recipient:
            # Fix invalid email
            modified_payload = EmailPayload(
                recipient=f"{payload.recipient}@example.com",
                subject=payload.subject,
                body=payload.body
            )
            return EmailResult(
                modified_payload=modified_payload,
                metadata={"fixed_email": True}
            )

        return EmailResult(continue_processing=True)
```

### Plugin Structure

Create a new directory under `plugins/`:

```
plugins/my_plugin/
├── __init__.py
├── plugin-manifest.yaml
├── my_plugin.py
└── README.md
```

### Plugin Manifest (`plugin-manifest.yaml`)

```yaml
description: "My custom plugin"
author: "Your Name"
version: "1.0.0"
available_hooks:
  - "tool_pre_invoke"
  - "tool_post_invoke"
default_configs:
  threshold: 0.8
  enable_logging: true
```

### Bootstrap from Template

```bash
mcpplugins bootstrap --destination plugins/my_plugin --type native
```

---

## Plugin Control Flow

### Hook Results

Each hook returns a result object that controls execution flow:

```python
# Allow processing to continue
return ToolPreInvokeResult(continue_processing=True)

# Modify the payload
return ToolPreInvokeResult(
    modified_payload=modified_payload,
    metadata={"processed": True}
)

# Block execution with a violation
from mcpgateway.plugins.framework import PluginViolation

return ToolPreInvokeResult(
    continue_processing=False,
    violation=PluginViolation(
        code="POLICY_VIOLATION",
        reason="Request blocked by security policy",
        description="Detected prohibited content"
    )
)
```

### Error Handling

Errors inside a plugin are handled based on configuration:

1. If `plugin_settings.fail_on_plugin_error` is `true`, the exception is bubbled up as a PluginError
2. If `plugin_settings.fail_on_plugin_error` is `false`, behavior depends on plugin mode:
   - **`enforce`**: Both violations and errors block execution
   - **`enforce_ignore_error`**: Violations block, errors are logged
   - **`permissive`**: Both violations and errors are logged, execution continues

---

## Performance Characteristics

The plugin framework is designed for production workloads:

- **1,000+ requests/second** with 5 active plugins
- **Sub-millisecond latency** for self-contained plugins (<1ms)
- **Parallel execution** within priority bands
- **Resource isolation** and timeout protection
- **Configurable timeouts** per plugin

### Latency Guidelines

- **Self-contained plugins**: <1ms target
- **External service plugins**: <100ms target
- Use async/await for I/O operations
- Implement timeouts for external calls

---

## External Service Plugins (MCP-based)

External plugins run as separate MCP servers, enabling microservice architectures:

```yaml
plugins:
  - name: "ExternalFilter"
    kind: "external"
    priority: 10
    mode: "enforce"
    mcp:
      proto: STREAMABLEHTTP    # or STDIO
      url: http://localhost:8000/mcp
      # tls:
      #   ca_bundle: /path/to/ca.crt
```

Required tools on external server:
- `get_plugin_config`
- `prompt_pre_fetch`, `prompt_post_fetch`
- `tool_pre_invoke`, `tool_post_invoke`
- `resource_pre_fetch`, `resource_post_fetch`

---

## Plugin Context and State

The `context` parameter provides access to request-scoped and global state:

```python
async def tool_pre_invoke(
    self,
    payload: ToolPreInvokePayload,
    context: PluginContext
) -> ToolPreInvokeResult:
    # Access request ID
    request_id = context.global_context.request_id

    # Access user information
    user = context.global_context.user
    tenant_id = context.global_context.tenant_id

    # Store plugin-specific state (persists across all hooks in the request)
    context.state["invocation_count"] = context.state.get("invocation_count", 0) + 1

    # Add metadata
    context.metadata["processing_time"] = 0.123

    return ToolPreInvokeResult(continue_processing=True)
```

---

## Testing Plugins

### Unit Testing

```python
import pytest
from mcpgateway.plugins.framework import (
    PluginConfig,
    PluginContext,
    GlobalContext,
    ToolPreInvokePayload,
)
from plugins.my_plugin.my_plugin import MyPlugin

@pytest.fixture
def plugin():
    config = PluginConfig(
        name="test_plugin",
        description="Test",
        version="1.0",
        author="Test",
        kind="plugins.my_plugin.my_plugin.MyPlugin",
        hooks=["tool_pre_invoke"],
        config={"threshold": 0.8}
    )
    return MyPlugin(config)

@pytest.mark.asyncio
async def test_tool_pre_invoke(plugin):
    payload = ToolPreInvokePayload(
        name="test_tool",
        args={"arg1": "value1"}
    )
    context = PluginContext(
        global_context=GlobalContext(request_id="test-123")
    )

    result = await plugin.tool_pre_invoke(payload, context)

    assert result.continue_processing is True
    assert result.modified_payload.args["plugin_processed"] is True
```

### Integration Testing

```bash
# Test with live gateway
make dev
curl -X POST http://localhost:4444/tools/invoke \
  -H "Content-Type: application/json" \
  -d '{"name": "test_tool", "arguments": {}}'
```

---

## Security Features

The plugin framework includes comprehensive security features:

- **Input validation and sanitization**
- **Timeout protection** for external calls
- **Resource limits** and quota enforcement
- **Error isolation** between plugins
- **Comprehensive audit logging**
- **Plugin configuration validation**
- **Hook signature validation** at plugin load time

---

## Real-World Example: API Connect FAM Plugin

To illustrate the power and flexibility of ContextForge's plugin framework, consider the **API Connect FAM Plugin** — a production-grade example that demonstrates enterprise-level plugin capabilities.

### What is the API Connect FAM Plugin?

The API Connect FAM Plugin is a sophisticated background agent that automatically synchronizes ContextForge's virtual servers, tools, and resources with IBM's Federated API Management (FAM) system. It showcases how ContextForge plugins can go beyond simple request/response hooks to implement complex, stateful, enterprise-grade integrations.

### Key Capabilities

This plugin demonstrates several advanced plugin patterns:

- **Background Task Orchestration**: Runs independently of request/response cycles using asyncio background tasks
- **Activity-Based Architecture**: Implements modular activities (RegisterRuntime, SendHeartbeat, SyncServers, SyncTools, SendMetrics) following enterprise agent patterns
- **Automatic Recovery**: Zero data loss through persistent state tracking and recovery mechanisms
- **Resilience Patterns**: Retry logic with exponential backoff, circuit breaker patterns, and graceful degradation
- **Smart Change Detection**: Uses SHA-256 content hashing to detect changes and minimize unnecessary API calls
- **Enterprise Observability**: Per-activity statistics, health monitoring, and comprehensive audit logging
- **Runtime Auto-Registration**: Automatically registers ContextForge as a runtime in FAM on startup

### Architecture Highlights

The plugin follows clean architecture principles with clear separation of concerns:

```
plugins/apiconnect_fam/
├── apiconnect_fam.py        # Main plugin orchestration
├── activity_orchestrator.py  # Activity scheduling and execution
├── fam_client.py            # FAM API client with retry logic
├── activities/              # Modular activity implementations
│   ├── register_runtime.py
│   ├── send_heartbeat.py
│   ├── sync_servers.py
│   ├── sync_tools.py
│   └── send_metrics.py
└── handlers/                # Recovery and error handling
    └── recovery_handler.py
```

### Integration Pattern

Unlike typical plugins that implement MCP protocol hooks, the API Connect FAM Plugin demonstrates how plugins can:

1. **Run Independently**: Uses background tasks instead of request/response hooks
2. **Maintain State**: Tracks synchronization state across restarts
3. **Integrate External Systems**: Communicates with enterprise APIs (FAM Asset Catalog API)
4. **Provide Observability**: Exposes statistics via plugin management API endpoints
5. **Handle Failures Gracefully**: Implements automatic recovery and retry mechanisms

### Configuration Example

```yaml
plugins:
  - name: "APIConnectFAM"
    kind: "plugins.apiconnect_fam.apiconnect_fam.APIConnectFAMPlugin"
    hooks: []  # No hooks - uses background task
    mode: "permissive"
    priority: 1000
    config:
      # Core settings
      interval_seconds: 60
      fam_enabled: true
      fam_base_url: "https://fam.example.com"
      fam_runtime_id: "prod-runtime-001"
      fam_auth_token: "${FAM_AUTH_TOKEN}"
      
      # Resilience settings
      retry_max_attempts: 3
      retry_backoff_factor: 2.0
      circuit_breaker_threshold: 5
      circuit_breaker_timeout: 300
      
      # Activity intervals
      heartbeat_interval: 30
      metrics_interval: 60
      sync_interval: 120
```

### Why This Matters

The API Connect FAM Plugin demonstrates that ContextForge's plugin framework is not just for simple content filtering or validation. It's a **production-ready platform** for building sophisticated, enterprise-grade integrations that require:

- Complex state management
- Background processing
- External system integration
- Automatic recovery and resilience
- Comprehensive observability

This makes ContextForge suitable for mission-critical AI infrastructure where reliability, observability, and enterprise integration are paramount.

For detailed architecture and implementation details, see the [API Connect FAM Plugin HLD Refinement](plugins/apiconnect_fam/docs/HLD_REFINEMENT.md) document.

---

## Use Cases

### AI Safety & Content Moderation

- Detect and block harmful content
- Apply content moderation policies
- Integrate with LlamaGuard, OpenAI Moderation
- Custom safety classifiers

### Compliance & Data Protection

- PII detection and masking
- GDPR compliance
- Data residency enforcement
- Audit logging and compliance reporting

### Security & Access Control

- Custom authentication mechanisms
- Fine-grained authorization
- IP-based access control
- Time-based access restrictions

### Performance Optimization

- Response caching
- Request batching
- Data compression
- Rate limiting

### Integration & Transformation

- Protocol translation
- Data normalization
- Format conversion
- Legacy system integration

---

## Getting Started

### 1. Install ContextForge

```bash
# Via PyPI
pip install mcp-contextforge-gateway

# Via Docker
docker pull ghcr.io/ibm/mcp-context-forge:latest
```

### 2. Enable Plugins

```bash
# In .env
PLUGINS_ENABLED=true
PLUGINS_CONFIG_FILE=plugins/config.yaml
```

### 3. Configure Your First Plugin

```yaml
# plugins/config.yaml
plugins:
  - name: "PIIFilterPlugin"
    kind: "plugins.pii_filter.pii_filter.PIIFilterPlugin"
    hooks: ["prompt_pre_fetch", "tool_pre_invoke"]
    mode: "enforce"
    priority: 50
    config:
      detect_ssn: true
      detect_email: true
      default_mask_strategy: "partial"
```

### 4. Start the Gateway

```bash
make dev
```

---

## Resources

- **Full Documentation**: https://ibm.github.io/mcp-context-forge/
- **Plugin Guide**: https://ibm.github.io/mcp-context-forge/using/plugins/
- **GitHub Repository**: https://github.com/IBM/mcp-context-forge
- **Plugin Examples**: See `plugins/` directory for 40+ implementations
- **Issue Tracker**: https://github.com/IBM/mcp-context-forge/issues

---

## Conclusion

ContextForge's plugin framework provides a production-ready foundation for building extensible, secure, and performant AI gateways. With 40+ built-in plugins, three flexible hook registration patterns, and support for both native Python and external MCP-based plugins, it enables teams to implement custom AI safety policies, content moderation, security controls, and operational excellence at scale.

Whether you're building a simple content filter or a complex multi-service AI safety pipeline, ContextForge's plugin framework provides the tools and patterns you need to succeed.