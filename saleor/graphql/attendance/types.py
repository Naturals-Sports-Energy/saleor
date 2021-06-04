from ..core.connection import CountableDjangoObjectType
import graphene
from graphene import relay
from ..meta.types import ObjectWithMetadata
from ...attendance import models

class Attendance(CountableDjangoObjectType):
    name = graphene.String(description="full name of user.")
    email = graphene.String(description="email of user.")
    time = graphene.String(description="time of attendance.")
    
    class Meta:
        description = "Represents a subscription in the shop."
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.Attendance
        only_fields = [
        ]
    
    @staticmethod
    def resolve_name(root: models.Attendance, _info):
        return "{} {}".format(root.user.first_name, root.user.last_name)

    @staticmethod
    def resolve_email(root: models.Attendance, _info):
        return root.user.email

    @staticmethod
    def resolve_time(root: models.Attendance, _info):
        return root.time.strftime("%I:%M:%S %p")

