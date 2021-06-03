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

logger = logging.getLogger(__name__)

class AttendanceType(CountableDjangoObjectType):
    isMarked = graphene.Boolean(description="tells wether attendance was marked or not.")
    class Meta:
        model = Attendance
    @staticmethod
    def resolve_isMarked(root: Attendance, _info):
        if root is None:
            return False
        else:
            return True

class MarkAttendance(graphene.Mutation):
    class Arguments:
        hash = graphene.String(required=True, description="hash from the qr code.")
    attendance = graphene.Field(AttendanceType)
    @classmethod
    def mutate(cls, root, info, hash=None):
        user = info.context.user
        date = datetime.today().date()

        #check if attendance is already marked
        attendance = Attendance.objects.filter(user=user).filter(date=date).first()
        if attendance is not None:
            logger.debug("attendance already marked")
            return MarkAttendance(attendance=attendance)
        # verify hash
        date = datetime.today().date()
        if verify(hash):
            # mark attendance
            attendance = Attendance(user=user, date=date)
            attendance.save()
        else:
            logger.debug("Invalid hash")
            attendance = None
            
        return MarkAttendance(attendance=attendance)
class AttendanceMutations(graphene.ObjectType):
    mark_attendance = MarkAttendance.Field()