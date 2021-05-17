import graphene
from graphene_django import DjangoObjectType
from ...account.types import AddressInput
from ....subscriptions.models import Subscription
from ....subscriptions import SubscriptionFrequency, SubscriptionStatus
from ....graphql.core.enums import to_enum
import graphene
from django.conf import settings

SubscriptionFrequencyEnum = to_enum(SubscriptionFrequency, type_name="SubscriptionFrequencyEnum")


class SubscriptionType(DjangoObjectType):
    class Meta:
        model = Subscription

class SubscriptionCreateInput(graphene.InputObjectType):
    shipping_method_id = graphene.ID(required=True, description="Shipping method.")
    shipping_address = AddressInput(
        description=(
            "The mailing address to where the checkout will be shipped. "
            "Note: the address will be ignored if the checkout "
            "doesn't contain shippable items."
        )
    )
    billing_address = AddressInput(description="Billing address of the customer.")
    variant_id = graphene.ID(required=True, description="Shipping method.")
    quantity = graphene.Int(required=True)
    frequency = graphene.Argument(
            SubscriptionFrequencyEnum, required=True, description="Subscription Frequency"
    )

class SubscriptionCreate(graphene.Mutation):
    class Arguments:
        input = SubscriptionCreateInput(
            required=True, description="Fields required to create checkout."
        )
    subscription = graphene.Field(SubscriptionType)
    @classmethod
    def mutate(cls, root, info, input=None):
        user = info.context.user
        print("******************************")
        print("frequency: {}".format(input.frequency))
        subscription = Subscription(
            billing_address= input.billing_address,
            shipping_address= input.shipping_address,
            shipping_method_id=input.shipping_method_id,
            variant_id=input.variant_id,
            quantity=input.quantity,
            user=user,
            frequency=input.frequency
        )
        subscription.save()
        # Notice we return an instance of this mutation
        return SubscriptionCreate(subscription=subscription)
    @classmethod
    def get_address(cls, address):
        first_name = address.first_name
        last_name = address.last_name
        company_name = address.company_name
        street_address_1 = address.street_address_1
        street_address_2 = address.street_address_2
        city = address.city
        city_area = address.city_area
        postal_code = address.postal_code
        country = address.country
        country_area = address.country_area
        phone = address.phone

class SubscriptionMutations(graphene.ObjectType):
    subscription_create = SubscriptionCreate.Field()