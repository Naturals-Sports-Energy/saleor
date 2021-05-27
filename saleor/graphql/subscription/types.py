from ..core.connection import CountableDjangoObjectType
import graphene
from graphene import relay
from ..meta.types import ObjectWithMetadata
from ...subscriptions import models

class Subscription(CountableDjangoObjectType):
    number = graphene.String(description="User-friendly number of an order.")
    
    class Meta:
        description = "Represents a subscription in the shop."
        interfaces = [relay.Node, ObjectWithMetadata]
        model = models.Subscription
    
    @staticmethod
    def resolve_number(root: models.Subscription, _info):
        return str(root.pk)