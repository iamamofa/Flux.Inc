# tasks.py
from celery import shared_task
from django.conf import settings
from .models import MSDSFile
import pyclamd
import logging

logger = logging.getLogger(__name__)

@shared_task
def scan_file_for_viruses(msds_id):
    msds = MSDSFile.objects.get(pk=msds_id)

    if not settings.CLAMAV_ENABLED:
        msds.scan_result = 'clean'
        msds.save()
        return

    try:
        cd = pyclamd.ClamdUnixSocket(settings.CLAMAV_SOCKET)
        file_path = msds.file.path

        scan_result = cd.scan_file(file_path)
        if scan_result is None:
            msds.scan_result = 'clean'
        else:
            virus = scan_result.get(file_path, 'Unknown virus')
            msds.scan_result = 'infected'
            logger.warning(f"Virus found in MSDS file {msds_id}: {virus}")

        msds.save()
    except Exception as e:
        logger.error(f"Virus scan failed for MSDS {msds_id}: {str(e)}")
        msds.scan_result = 'error'
        msds.save()
