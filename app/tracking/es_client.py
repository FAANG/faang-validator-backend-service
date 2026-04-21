import os
from typing import Optional

from elasticsearch import Elasticsearch
from dotenv import load_dotenv


# Load environment variables from .env file
load_dotenv()


_es_client: Optional[Elasticsearch] = None


def get_es_client() -> Elasticsearch:
    global _es_client
    if _es_client is None:
        try:
            node = os.environ['ES_URL']
            user = os.environ['ES_USERNAME']
            password = os.environ['ES_PASSWORD']
        except KeyError as missing:
            raise RuntimeError(
                f"Submission tracking requires env var {missing.args[0]} "
                "to be set (ES_URL, ES_USER, ES_PASSWORD)."
            ) from None

        _es_client = Elasticsearch(
            [node],
            basic_auth=(user, password),
            verify_certs=True,
        )
    return _es_client


def reset_es_client() -> None:
    global _es_client
    _es_client = None
