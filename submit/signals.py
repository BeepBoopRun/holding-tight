from django.db.models.signals import post_delete
from django.dispatch import receiver

from .models import Submission

@receiver(post_delete, sender=Submission)
def signal_function_name(sender, instance, using, **kwargs):
    submission_path = Path(settings.MEDIA_ROOT).joinpath(str(submission_id))
