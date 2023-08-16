import json
import logging.config
import os


def configure_logging():
    class UvicornFormatter(logging.Formatter):
        def format(self, record):
            level_colors = {
                logging.DEBUG: "\033[32m",  # 绿色
                logging.INFO: "\033[36m",  # 青色
                logging.WARNING: "\033[33m",  # 黄色
                logging.ERROR: "\033[31m",  # 红色
                logging.CRITICAL: "\033[35m",  # 紫色
            }
            level_name = record.levelname
            level_color = level_colors.get(record.levelno, "")
            reset_color = "\033[0m"
            record.levelname = f"{level_color}{level_name}{reset_color}"
            return super().format(record)

    logging.config.dictConfig({
        "version": 1,
        "disable_existing_loggers": False,
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "formatter": "uvicorn",
            },
        },
        "formatters": {
            "uvicorn": {
                "()": UvicornFormatter,
                "format": "%(levelname)s:     %(message)s",
            },
        },
        "loggers": {
            "": {
                "handlers": ["console"],
                "level": "INFO",
            },
        },
    })


configure_logging()
logger = logging.getLogger(__name__)


def load_configure(config_file: str = "./default.json") -> dict:
    if os.path.exists(config_file):
        with open(config_file, "r") as f:
            try:
                config = json.load(f)
                if isinstance(config, dict):
                    return config
                else:
                    raise json.JSONDecodeError
            except json.JSONDecodeError as e:
                warn_msg = f"{config_file} is not a valid json file"
                logger.error(warn_msg)
                raise e
    else:
        err_msg = f"FIle {config_file} is not existed."
        logger.error(err_msg)
        raise FileNotFoundError(err_msg)


def load_openai_key(config: dict):
    if config['openai']["api_key"]:
        return config['openai']["api_key"]
    elif os.getenv('OPENAI_API_KEY'):
        return os.getenv('OPENAI_API_KEY')
    else:
        logger.error(f"Could not find openai API key")
        raise ValueError(f"Could not find openai API key")


def load_openai_base(config: dict) -> str:
    if config['openai']["api_base"]:
        return config['openai']["api_base"]
    else:
        return "https://api.openai.com"


def parse_glossary(config: dict) -> dict:
    if 'glossary' in config.keys() and config['glossary'] and os.path.exists(config['glossary']):
        with open(config["glossary"]) as f:
            try:
                glossary = json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Glossary \"{config['glossary']}\" is not a valid json file")
                return {}
            logger.info(f"Glossary {config['glossary']} for openai parsed success")
            return glossary
    else:
        logger.warning(f"The glossary is not configured or the glossary file does not exist")
        return {}
