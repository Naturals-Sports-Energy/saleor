from saleor import subscriptions
import graphene
from graphene_django import DjangoObjectType
from graphene import relay
from graphene_django.filter import DjangoFilterConnectionField

from ...subscriptions.models import Subscription

class SubscriptionNode(DjangoObjectType):
    class Meta:
        model = Subscription
        filter_fields = ['status', 'created','user']
        interfaces = (relay.Node, )

class SubscriptionQueries(graphene.ObjectType):
    subscription = relay.Node.Field(SubscriptionNode)
    subscriptions = DjangoFilterConnectionField(SubscriptionNode)
