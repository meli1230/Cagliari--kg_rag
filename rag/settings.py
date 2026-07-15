import os

from dotenv import load_dotenv

load_dotenv()


class Settings:
    LLAMA_API_KEY = os.getenv("LLAMA_API_KEY")
    LLAMA_MODEL = os.getenv("LLAMA_MODEL")

    @classmethod
    def validate(cls) -> None:
        missing = []

        if not cls.LLAMA_API_KEY:
            missing.append("LLAMA_API_KEY")

        if not cls.LLAMA_MODEL:
            missing.append("LLAMA_MODEL")

        if missing:
            raise RuntimeError(f"Missing environment variables: {', '.join(missing)}")