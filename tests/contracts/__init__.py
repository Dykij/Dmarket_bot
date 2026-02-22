"""Contract tests for DMarket API using Pact.

This package contains consumer-driven contract tests that verify
the API contracts between the DMarket Telegram Bot (consumer)
and the DMarket API (provider).

Contract testing ensures that:
1. The consumer (bot) sends requests that the provider (API) understands
2. The provider (API) returns responses that the consumer (bot) can handle
3. Both parties agree on the contract without tight coupling

For more information, see docs/CONTRACT_TESTING.md
"""
