from loguru import logger

@logger.catch
def get_logger():
    # Configure logging
    logger.add("output.log", rotation="500 MB")
    logger.opt(ansi=True)
    return logger


def log_chat_input(text):
    logger.opt(ansi=True).info(f'---| <y>USER</y>  | <i>{text}</i>')

def log_chat_output(text):
    logger.opt(ansi=True).info(f'--| <g>ATLAS</g> | <i>{text}</i>')

