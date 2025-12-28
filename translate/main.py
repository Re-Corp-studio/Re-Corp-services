from dataclasses import dataclass, asdict, replace
from googleapiclient.discovery import build
from google.oauth2 import service_account
from google.cloud import translate_v2 as translate
import logging
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
import time


@dataclass
class State:
    """Represents the current state of the document translation service."""

    last_modified: Optional[str] = "1970-01-01T00:00:00"
    last_content_hash: Optional[int] = 0

    @classmethod
    def from_dict(cls, data: dict) -> "State":
        return cls(**data)

    def to_dict(self) -> dict:
        return asdict(self)


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
)

ENV_LOCAL = Path.cwd() != Path("/opt/translate")

# Google API setup
SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/cloud-platform",  # Required for Translation API
]
if ENV_LOCAL:
    SERVICE_ACCOUNT_FILE = Path("./service-account.json")
    STATE_FILE = Path("./state.json")
else:
    SERVICE_ACCOUNT_FILE = Path("/opt/translate/service-account.json")
    STATE_FILE = Path("/var/lib/translate/state.json")

# 5 minutes default
POLL_INTERVAL = 300

# "концепция игры"
SOURCE_DOC_ID = "1L__8cyRWhVrGUxiEsNANAev1FPDXFxSFWbUZBBUSNLU"
SOURCE_LANGUAGE = "ru"

# "game concept (readonly)"
TARGET_DOC_ID = "1AABlfwV6vlQSaCZLTklbvzm-Qd4V7RT5Gqww-sZNuFM"
TARGET_LANGUAGE = "en"


try:
    credentials = service_account.Credentials.from_service_account_file(
        str(SERVICE_ACCOUNT_FILE), scopes=SCOPES
    )
    drive_service = build("drive", "v3", credentials=credentials)
    docs_service = build("docs", "v1", credentials=credentials)
    translate_client = translate.Client(credentials=credentials)
except Exception as e:
    logger.error(f"Failed to initialize Google API services: {e}")
    exit(1)


def load_state() -> State:
    """Load the last known state of the document."""
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE, "r") as f:
                data = json.load(f)
                return State.from_dict(data)
        except Exception as e:
            logger.warning(f"Could not load state file: {e}")
    return State()


def save_state(state: State):
    """Save the current state of the document."""
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state.to_dict(), f, indent=2)
    except Exception as e:
        logger.error(f"Could not save state file: {e}")


def translate_and_update(previous_state: State) -> State:
    next_state = replace(previous_state)
    try:
        logger.debug(f"Checking document {SOURCE_DOC_ID} for changes...")

        # compare modification time
        file_metadata = (
            drive_service.files()
            .get(fileId=SOURCE_DOC_ID, fields="modifiedTime")
            .execute()
        )
        modified_time = file_metadata.get("modifiedTime").rstrip("Z")
        if modified_time == previous_state.last_modified:
            # no modification
            return next_state

        logger.info(f"Document modified time changed: {modified_time}")
        next_state.last_modified = modified_time

        # compare document content
        document = docs_service.documents().get(documentId=SOURCE_DOC_ID).execute()
        content = ""
        for element in document.get("body", {}).get("content", []):
            if "paragraph" in element:
                for text_element in element["paragraph"].get("elements", []):
                    content += text_element.get("textRun", {}).get("content", "")
        content_hash = hash(content)
        if content_hash == previous_state.last_content_hash:
            # no content change
            return next_state

        logger.info("Document content changed, starting translation...")
        next_state.last_content_hash = content_hash

        # translate the content
        content = content.replace("\n", "<br>")
        result = translate_client.translate(
            content,
            target_language=TARGET_LANGUAGE,
            source_language=SOURCE_LANGUAGE,
            format_="html",
        )
        translated_content = result["translatedText"].replace("<br>", "\n")

        # update target document
        target_doc = docs_service.documents().get(documentId=TARGET_DOC_ID).execute()
        doc_content = target_doc.get("body", {}).get("content", [])

        # Calculate end index (total length of document)
        end_index = 1
        for element in doc_content:
            if "paragraph" in element:
                end_index = element.get("endIndex", end_index)

        # prepare new content with timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_content = f"Translated on {timestamp}\n\n{translated_content}"

        # replace all document content
        docs_service.documents().batchUpdate(
            documentId=TARGET_DOC_ID,
            body={
                "requests": [
                    {
                        "deleteContentRange": {
                            "range": {"startIndex": 1, "endIndex": end_index - 1}
                        }
                    },
                    {
                        "insertText": {
                            "location": {"index": 1},
                            "text": new_content,
                        }
                    },
                ]
            },
        ).execute()

        logger.info("Translation completed.")
    except Exception as e:
        logger.error(f"Error in translation process: {e}")

    return next_state


def main():
    """Main service loop."""
    logger.info("Translation service starting...")
    logger.info(f"Monitoring document: {SOURCE_DOC_ID}")
    logger.info(f"Target language: {TARGET_LANGUAGE}")
    logger.info(f"Poll interval: {POLL_INTERVAL} seconds")

    state = load_state()

    while True:
        try:
            state = translate_and_update(previous_state=state)
            save_state(state)
        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")

        time.sleep(POLL_INTERVAL)


if __name__ == "__main__":
    main()
