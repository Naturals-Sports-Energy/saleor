from saleor import subscriptions
import graphene
from graphene_django import DjangoObjectType
from graphene import relay
from graphene_django.fields import DjangoConnectionField
from ..core.fields import FilterInputConnectionField
from ..core.types import SortInputObjectType
from ..core.types import FilterInputObjectType
import django_filters

from ...subscriptions.models import Subscription


class SubscriptionFilter(django_filters.FilterSet):
    class Meta:
        model = Subscription
        fields = ['status', 'created','user']


class SubscriptionFilterInput(FilterInputObjectType):
    class Meta:
        filterset_class = SubscriptionFilter

class SubscriptionSortField(graphene.Enum):
    NUMBER = ["pk"]
    CREATION_DATE = ["created", "status", "pk"]

class SubscriptionSortingInput(SortInputObjectType):
    class Meta:
        sort_enum = SubscriptionSortField
        type_name = "orders"

class SubscriptionNode(DjangoObjectType):
    number = graphene.String(description="User-friendly number of a subscription.")
    class Meta:
        model = Subscription
        filter_fields = ['status', 'created','user']
        interfaces = (relay.Node, )

    @staticmethod
    def resolve_number(root: Subscription, _info):
        return str(root.pk)

class SubscriptionQueries(graphene.ObjectType):
    subscription = relay.Node.Field(SubscriptionNode)
    subscriptions = DjangoConnectionField(
        SubscriptionNode,
        sort_by=SubscriptionSortingInput(description="Sort orders."),
        filter=SubscriptionFilterInput(description="Filtering options for orders."),
    )
