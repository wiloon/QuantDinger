"""
Entrypoint: python -m mt5_gateway.run
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend_api_python"))

from app.utils.logger import get_logger, setup_logger  # noqa: E402
from mt5_gateway.app import create_app, register_shutdown  # noqa: E402

logger = get_logger("mt5_gateway")


def main():
    setup_logger()
    host = os.environ.get("MT5_GATEWAY_HOST", "127.0.0.1")
    port = int(os.environ.get("MT5_GATEWAY_PORT", "5100"))
    app = create_app()
    register_shutdown(app)
    logger.info("Starting MT5 Gateway on %s:%s", host, port)
    logger.info("Health: http://%s:%s/health", host, port)
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
