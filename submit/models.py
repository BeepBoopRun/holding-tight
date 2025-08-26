from django.db import models

import uuid


class Submission(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True, default=None)
    name_VOI = models.CharField(null=True, blank=True, default=None)
    email = models.EmailField(null=True, blank=True, default=None)
    common_numbering = models.BooleanField()


class SubmittedForm(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE)
    form_id = models.IntegerField()
    value = models.FloatField()
    name = models.CharField(null=True, blank=True, default=None)

    FILE_INPUT_TYPES = (
        ("M", "MaestroDir"),
        ("T", "TopTrjPair"),
    )
    file_input = models.CharField(max_length=1, choices=FILE_INPUT_TYPES)


class SubmissionTask(models.Model):
    submission = models.ForeignKey(Submission, on_delete=models.CASCADE)

    class TaskStatus(models.TextChoices):
        PENDING = "P", "Pending"
        RUNNING = "R", "Running"
        FAILED = "F", "Failed"
        SUCCESS = "S", "Success"

    status = models.CharField(max_length=1, choices=TaskStatus)

    class TaskType(models.TextChoices):
        NUMBERING = "N", "Numbering"
        INTERACTIONS = "I", "Calculating interactions"

    task_type = models.CharField(max_length=1, choices=TaskType)
