from django.db import models
from ..account.models import User
from django.utils.timezone import now

class Attendance(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    date = models.DateField(default=now, editable=False)
    time = models.TimeField(default=now, editable=False)
