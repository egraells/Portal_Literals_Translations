import os
import argparse
import pycountry
from dotenv import load_dotenv
from logger_manager import LoggerManager


class EnvVariableManager:
    def __init__(self, logger_manager) -> None:

        self.logger = logger_manager.get_logger()
        self._OPENAI_MODEL = ""
        self._OPENAI_API_KEY = ""
        self.load_env_variables()

    def load_env_variables(self) -> None:
        load_dotenv()

        self._CLIENT_ID = os.getenv("CLIENT_ID", "")
        self._CLIENT_SECRET = os.getenv("CLIENT_SECRET", "")
        self._TOKEN_URL = os.getenv("TOKEN_URL", "")

        # In case you use an OpenAI compatible LLM
        self._OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
        self._OPENAI_MODEL = os.getenv("OPENAI_MODEL", "")

    def parse_arguments(self):
        parser = argparse.ArgumentParser(description="Translations using AI for Salesforce.")
        parser.add_argument("--source_xlf_file", type=str, help="Path to the source translations XLF file containing the translations that we want to translate.")
        parser.add_argument("--target_xlf_file", type=str, help="Path to the target XLF file that will be created with the literals translated.")
        parser.add_argument("--target_xlf_file_baseline", type=str, default=None, help="Path to the baseline target XLF file, this file is useful if you already have a file with translations that you don't want to translate again.")
        parser.add_argument("--target_language_iso", type=str, help="Letters in the iso format for the target_language, i.e.: ca, ES-es, etc.")
        parser.add_argument("--llm_batch_size", type=int, default=50, help="Number of rows to process in each API call to the LLM.")
        parser.add_argument("--prompt_addition_file", type=str, default="", help="Additional instructions for the LLM that will be added at the end of the prompt")
        parser.add_argument("--exclusion_file", type=str, default="", help="Path to a text file containing literals to exclude one per line.")
        parser.add_argument("--exclusion_patterns", type=str, default="", help="Comma-separated list of patterns to exclude.")

        args = parser.parse_args()

        # Is the file from prompt_addition path valid ?
        if not (args.prompt_addition_file and os.path.exists(args.prompt_addition_file)):
            self.logger.warning(f"Prompt addition file: '{args.exclusion_file}' not found or empty.")
            exit(1)

        # Read the exclusion file if provided
        if not (args.exclusion_file and os.path.exists(args.exclusion_file)):
            self.logger.warning(f"Exclusion file not found or empty.")

        self.logger.info(
            f"Parameters received - input_file: {args.source_xlf_file},"
            f"target_xlf_file: {args.target_xlf_file}",
            f"target_xlf_file_baseline: {args.target_xlf_file_baseline}, "
            f"target_language: {args.target_language_iso}, "
            f"llm_batch_size: {args.llm_batch_size}, "
            f"prompt_addition_file: {args.prompt_addition_file}"
            f"exclusion_file: {args.exclusion_file}",
            f"exclusion_patterns: {args.exclusion_patterns}",
        )

        return args
