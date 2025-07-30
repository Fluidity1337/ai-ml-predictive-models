import requests
import logging

def send_discord_webhook(message: str, webhook_url: str, file_path: str = None, file_label: str = None):
    """
    Send a message (and optional file) to a Discord webhook.
    Args:
        message (str): The message to send.
        webhook_url (str): The Discord webhook URL.
        file_path (str, optional): Path to a file to send as attachment.
        file_label (str, optional): Label for the file (default: filename).
    """
    data = {"content": message}
    files = None
    if file_path:
        try:
            with open(file_path, "rb") as f:
                files = {"file": (file_label or file_path, f.read())}
                resp = requests.post(webhook_url, data=data, files=files, timeout=20)
        except Exception as e:
            logging.error(f"Failed to send file to Discord webhook: {e}")
            return False
    else:
        try:
            resp = requests.post(webhook_url, json=data, timeout=10)
        except Exception as e:
            logging.error(f"Failed to send Discord webhook: {e}")
            return False
    try:
        resp.raise_for_status()
        logging.info(f"Sent Discord webhook: {message}{' with file' if file_path else ''}")
    except Exception as e:
        logging.error(f"Discord webhook returned error: {e}")
        return False
    return True
