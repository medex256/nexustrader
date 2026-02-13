from dotenv import load_dotenv
import os
import logging

# Load environment variables from .env as early as possible.
load_dotenv()

# Suppress noisy Google gRPC ALTS warnings
os.environ["GRPC_VERBOSITY"] = "ERROR"
os.environ["GRPC_TRACE"] = ""
logging.getLogger("grpc").setLevel(logging.ERROR)

