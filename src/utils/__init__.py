"""Utils module.

This module provides various utility functions and classes for the DMarket Bot:

- Environment validation
- Graceful shutdown handling
- Health monitoring
- Feature flags management
- Discord notifications
- Prometheus metrics
- Rate limiting
- Retry decorators (tenacity + stamina)
- HTTP caching (hishel)
- Watchdog for bot supervision
"""

from src.utils.config import Config
from src.utils.exceptions import (
    APIError,
    BaseAppException,
    NetworkError,
    RateLimitExceeded,
)

# Optional imports - these may fail if dependencies are not installed
try:
    from src.utils.env_validator import validate_on_startup, validate_required_env_vars
except ImportError:
    validate_on_startup = None
    validate_required_env_vars = None

try:
    from src.utils.extended_shutdown_handler import (
        ExtendedShutdownHandler as ShutdownHandler,
    )
    from src.utils.extended_shutdown_handler import (
        extended_shutdown_handler as shutdown_handler,
    )
except ImportError:
    ShutdownHandler = None
    shutdown_handler = None

try:
    from src.utils.health_monitor import HealthCheckResult, HealthMonitor, ServiceStatus
except ImportError:
    HealthMonitor = None
    HealthCheckResult = None
    ServiceStatus = None

try:
    from src.utils.feature_flags import (
        Feature,
        FeatureFlagsManager,
        get_feature_flags,
        init_feature_flags,
    )
except ImportError:
    Feature = None
    FeatureFlagsManager = None
    get_feature_flags = None
    init_feature_flags = None

try:
    from src.utils.discord_notifier import (
        DiscordNotifier,
        NotificationLevel,
        create_discord_notifier_from_env,
    )
except ImportError:
    DiscordNotifier = None
    NotificationLevel = None
    create_discord_notifier_from_env = None

try:
    from src.utils.rate_limit_decorator import rate_limit
except ImportError:
    rate_limit = None

try:
    from src.utils.retry_decorator import retry_api_call, retry_on_failure
except ImportError:
    retry_api_call = None
    retry_on_failure = None

try:
    from src.utils.stamina_retry import (
        STAMINA_AVAILABLE,
        api_retry,
        async_disabled_retries,
        disabled_retries,
        retry_async,
        retry_sync,
    )
except ImportError:
    STAMINA_AVAILABLE = False
    api_retry = None
    async_disabled_retries = None
    disabled_retries = None
    retry_async = None
    retry_sync = None

try:
    from src.utils.http_cache import (
        HISHEL_AVAILABLE,
        CacheConfig,
        CachedHTTPClient,
        close_cached_client,
        create_cached_client,
        get_cached_client,
    )
except ImportError:
    HISHEL_AVAILABLE = False
    CachedHTTPClient = None
    CacheConfig = None
    close_cached_client = None
    create_cached_client = None
    get_cached_client = None

try:
    from src.utils.watchdog import Watchdog, WatchdogConfig
except ImportError:
    Watchdog = None
    WatchdogConfig = None

try:
    from src.utils.enhanced_api import (
        EnhancedAPIConfig,
        EnhancedHTTPClientMixin,
        create_enhanced_http_client,
        create_retry_decorator,
        enhance_dmarket_method,
        enhance_waxpeer_method,
        get_api_enhancement_status,
    )
except ImportError:
    EnhancedAPIConfig = None
    EnhancedHTTPClientMixin = None
    create_enhanced_http_client = None
    create_retry_decorator = None
    enhance_dmarket_method = None
    enhance_waxpeer_method = None
    get_api_enhancement_status = None

try:
    from src.utils.aiometer_utils import (
        AIOMETER_AVAILABLE,
        ConcurrencyConfig,
        ConcurrentResult,
        amap,
        get_aiometer_status,
        run_batches,
        run_concurrent,
        run_with_rate_limit,
    )
except ImportError:
    AIOMETER_AVAILABLE = False
    ConcurrencyConfig = None
    ConcurrentResult = None
    amap = None
    get_aiometer_status = None
    run_batches = None
    run_concurrent = None
    run_with_rate_limit = None

try:
    from src.utils.asyncer_utils import (
        ASYNCER_AVAILABLE,
        ParallelResult,
        create_task_group,
        get_asyncer_status,
        run_all_settled,
        run_first_completed,
        run_parallel,
        run_sync_in_thread,
        run_with_timeout,
    )
except ImportError:
    ASYNCER_AVAILABLE = False
    ParallelResult = None
    create_task_group = None
    get_asyncer_status = None
    run_all_settled = None
    run_first_completed = None
    run_parallel = None
    run_sync_in_thread = None
    run_with_timeout = None


__all__ = [
    # Exceptions
    "APIError",
    "BaseAppException",
    # Config
    "Config",
    # Discord notifications
    "DiscordNotifier",
    # Feature flags
    "Feature",
    "FeatureFlagsManager",
    # Health monitoring
    "HealthCheckResult",
    "HealthMonitor",
    "NetworkError",
    "NotificationLevel",
    "RateLimitExceeded",
    "ServiceStatus",
    # Shutdown handling
    "ShutdownHandler",
    # Watchdog
    "Watchdog",
    "WatchdogConfig",
    "create_discord_notifier_from_env",
    "get_feature_flags",
    "init_feature_flags",
    # Rate limiting
    "rate_limit",
    # Retry decorators (tenacity)
    "retry_api_call",
    "retry_on_failure",
    # Retry decorators (stamina - production-grade)
    "STAMINA_AVAILABLE",
    "api_retry",
    "async_disabled_retries",
    "disabled_retries",
    "retry_async",
    "retry_sync",
    # HTTP caching (hishel)
    "HISHEL_AVAILABLE",
    "CachedHTTPClient",
    "CacheConfig",
    "close_cached_client",
    "create_cached_client",
    "get_cached_client",
    # Enhanced API integration
    "EnhancedAPIConfig",
    "EnhancedHTTPClientMixin",
    "create_enhanced_http_client",
    "create_retry_decorator",
    "enhance_dmarket_method",
    "enhance_waxpeer_method",
    "get_api_enhancement_status",
    # Concurrent execution (aiometer)
    "AIOMETER_AVAILABLE",
    "ConcurrencyConfig",
    "ConcurrentResult",
    "amap",
    "get_aiometer_status",
    "run_batches",
    "run_concurrent",
    "run_with_rate_limit",
    # Parallel execution (asyncer)
    "ASYNCER_AVAILABLE",
    "ParallelResult",
    "create_task_group",
    "get_asyncer_status",
    "run_all_settled",
    "run_first_completed",
    "run_parallel",
    "run_sync_in_thread",
    "run_with_timeout",
    # Watchdog
    "Watchdog",
    "WatchdogConfig",
    "shutdown_handler",
    # Environment validation
    "validate_on_startup",
    "validate_required_env_vars",
]
