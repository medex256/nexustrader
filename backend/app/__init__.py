import os
import logging
from dotenv import load_dotenv

# Load environment variables from the backend .env explicitly so the running
# backend does not inherit a stale project from another shell/session.
BACKEND_ENV_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(BACKEND_ENV_PATH, override=True)

logger = logging.getLogger(__name__)

# Suppress noisy Google gRPC ALTS warnings
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_TRACE"] = ""
logging.getLogger("grpc").setLevel(logging.ERROR)

logger.warning(
	"Backend env loaded: GOOGLE_CLOUD_PROJECT=%s | GOOGLE_VERTEX_API_KEY=%s",
	os.getenv("GOOGLE_CLOUD_PROJECT") or "<missing>",
	"present" if os.getenv("GOOGLE_VERTEX_API_KEY") else "<missing>",
)

