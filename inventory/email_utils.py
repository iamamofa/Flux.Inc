from email.mime.image import MIMEImage
from pathlib import Path

from django.conf import settings


def attach_inline_email_images(message, image_names):
    image_directory = Path(settings.BASE_DIR) / 'static' / 'images'
    for image_name in image_names:
        image_path = image_directory / image_name
        with image_path.open('rb') as image_file:
            image = MIMEImage(image_file.read())

        content_id = image_path.stem
        image.add_header('Content-ID', f'<{content_id}>')
        image.add_header('Content-Disposition', 'inline', filename=image_name)
        image.add_header('X-Attachment-Id', content_id)
        message.attach(image)
