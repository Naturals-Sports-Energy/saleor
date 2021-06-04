import graphene
from saleor.attendance import models
from ..core.fields import FilterInputConnectionField
from .types import Attendance
from ..core.fields import FilterInputConnectionField
from ..core.types import SortInputObjectType
from ..core.types import FilterInputObjectType
from ..core.connection import CountableDjangoObjectType
import django_filters

class AttendanceFilter(django_filters.FilterSet):
    class Meta:
        model = models.Attendance
        fields = ['date', 'time','user']

class AttendanceFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = AttendanceFilter

class AttendanceSortField(graphene.Enum):
    NUMBER = ["pk"]

class AttendanceSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = AttendanceSortField
        type_name = "attendance"

class AttendanceQueries(graphene.ObjectType):
    attendance = FilterInputConnectionField(
        Attendance,
        sort_by=AttendanceSortingInput(description="Sort attendance."),
        filter=AttendanceFilterInput(description="Filtering options for attendance"),
    )