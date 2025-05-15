import logging
import os

class LoggerManager:
    _instance = None  # Singleton instance

    BACKEND_LOG_FILE = os.getenv("LOG_FILE_BACKEND")
    def __new__(cls, log_file=BACKEND_LOG_FILE):
        if cls._instance is None:
            cls._instance = super(LoggerManager, cls).__new__(cls)

            cls._instance.logger = logging.getLogger("GlobalLogger")
            cls._instance.logger.setLevel(logging.DEBUG)

            # Create a file and a console handlers
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.DEBUG)

            console_handler = logging.StreamHandler()
            console_handler.setLevel(logging.DEBUG)

            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            file_handler.setFormatter(formatter)
            console_handler.setFormatter(formatter)

            # Add handlers to the logger for file and console
            cls._instance.logger.addHandler(file_handler)
            cls._instance.logger.addHandler(console_handler)

        return cls._instance

    def get_logger(self):

        return self.logger
