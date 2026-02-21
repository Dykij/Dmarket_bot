import structlog


def setup_logging(*args, **kwargs):
    pass


def get_logger(name="app"):
    return structlog.get_logger(name)


def BotLogger(name="bot"):
    return structlog.get_logger(name)
