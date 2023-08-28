"""Utility methods"""

from contextlib import suppress

from apps.catalog.models import Service, WriterTypeService


def get_service(paper_id, deadline_id, level_id=None):
    """Get the service if available

    Priority is always given to the service where level is None
    if it exists
    """
    service = None

    try:
        service = Service.objects.get(
            paper__id=paper_id, deadline__id=deadline_id, level=None
        )

    except Service.DoesNotExist:
        with suppress(Service.DoesNotExist):
            service = Service.objects.get(
                paper__id=paper_id, deadline__id=deadline_id, level__id=level_id
            )

    return service


def get_writer_type_service(paper_id, deadline_id, writer_type_id, level_id=None):
    """Get writer type price

    Priority is always given to the service where level is None
    if it exists"
    """
    writer_type_service = None
    service = get_service(paper_id, deadline_id, level_id)

    if service:
        with suppress(WriterTypeService.DoesNotExist):
            writer_type_service = WriterTypeService.objects.get(
                writer_type__id=writer_type_id, service=service
            )

    return writer_type_service
