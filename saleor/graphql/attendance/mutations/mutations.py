from graphene.types.scalars import Boolean
from saleor import attendance
from ...core.connection import CountableDjangoObjectType
from ....attendance.models import Attendance
import graphene
import hmac, hashlib
from hmac import compare_digest
from django.conf import settings
from datetime import datetime
from . import verify
import logging
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

class AttendanceType(CountableDjangoObjectType):
    class Meta:
        model = Attendance

class MarkAttendance(graphene.Mutation):

    class Arguments:
        hash = graphene.String(required=True, description="hash from the qr code.")
    attendance = graphene.Field(AttendanceType)
    is_marked = graphene.Boolean()
    error = graphene.String(default_value=None)
    @classmethod
    def mutate(cls, root, info, hash=None):
        user = info.context.user
        date = datetime.today().date()
        error = None

        #check if attendance is already marked
        attendance = Attendance.objects.filter(user=user).filter(date=date).first()
        if attendance is not None:
            logger.debug("attendance already marked")
            return MarkAttendance(attendance=attendance, is_marked=True)
        # verify hash
        date = datetime.today().date()
        if verify(hash):
            # mark attendance
            attendance = Attendance(user=user, date=date)
            attendance.save()
            is_marked = True
        else:
            logger.debug("Invalid hash")
            attendance = None
            is_marked = False
            error = "Invalid hash"
            
        return MarkAttendance(attendance=attendance, is_marked=is_marked, error=error)
class AttendanceMutations(graphene.ObjectType):
    mark_attendance = MarkAttendance.Field()