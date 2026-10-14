import os


def _env_bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in ("1", "true", "yes", "on")


REUSE_BROWSER: bool = _env_bool("SCRAPER_REUSE_BROWSER", True)
MAX_PAGES: int = int(os.getenv("SCRAPER_MAX_PAGES", "3"))
HEADLESS: bool = _env_bool("SCRAPER_HEADLESS", True)
BROWSER_IDLE_TIMEOUT: float = float(os.getenv("SCRAPER_BROWSER_IDLE_TIMEOUT", "300"))
BLOCK_PRIVATE_NETWORK: bool = _env_bool("SCRAPER_BLOCK_PRIVATE_NETWORK", False)
ADAPTIVE_DB_DIR: str = os.getenv("SCRAPER_ADAPTIVE_DB_DIR", "")

SCRAPER_HOST: str = os.getenv("SCRAPER_HOST", "127.0.0.1")
SCRAPER_PORT: int = int(os.getenv("SCRAPER_PORT", "18000"))
SCRAPER_LOG_LEVEL: str = os.getenv("SCRAPER_LOG_LEVEL", "INFO")

HUB_URL: str = os.getenv("HUB_URL", "http://127.0.0.1:3001")
HUB_REGISTER_URL: str = f"{HUB_URL}/api/mcp/tools/register"
