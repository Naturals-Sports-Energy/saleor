import graphene
from graphene_django import DjangoObjectType
from ....account.models import Address
from ...account.types import AddressInput
from ....product.models import ProductVariant
from ....subscriptions.models import Subscription
from ....subscriptions import SubscriptionFrequency, SubscriptionStatus
from ....graphql.core.enums import to_enum
import graphene
from django.conf import settings
from graphql_relay import from_global_id
from . import get_next_order_date
from datetime import date

SubscriptionFrequencyEnum = to_enum(SubscriptionFrequency, type_name="SubscriptionFrequencyEnum")


class SubscriptionType(DjangoObjectType):
    class Meta:
        model = Subscription

class SubscriptionCreateInput(graphene.InputObjectType):
    shipping_method_id = graphene.ID(required=True, description="Shipping method.")
    shipping_address_id = graphene.ID(required=True, description="shipping address id")
    billing_address_id = graphene.ID(required=True, description="billing address id")
    variant_id = graphene.ID(required=True, description="Shipping method.")
    quantity = graphene.Int(required=True)
    frequency = graphene.Argument(
            SubscriptionFrequencyEnum, required=True, description="Subscription Frequency"
    )
    token_customer_id = graphene.ID(required=True, description="TokenCustomerID")

class SubscriptionCancelInput(graphene.InputObjectType):
    subscription_id = graphene.ID(required=True, description="Subscription ID")

class SubscriptionCreate(graphene.Mutation):
    class Arguments:
        input = SubscriptionCreateInput(
            required=True, description="Fields required to create Subscription."
        )
    subscription = graphene.Field(SubscriptionType)
    @classmethod
    def mutate(cls, root, info, input=None):
        user = info.context.user
        print("******************************")
        print("frequency: {}".format(input.frequency))
        # product variant
        _, pk = from_global_id(input.variant_id)
        variant=ProductVariant.objects.get(pk=pk)

        # billing address
        _, pk = from_global_id(input.billing_address_id)
        billing_address=Address.objects.get(pk=pk)
        billing_address.pk = None
        billing_address.save()

        # shipping address
        _, pk = from_global_id(input.billing_address_id)
        shipping_address=Address.objects.get(pk=pk)
        shipping_address.pk = None
        shipping_address.save()

        today = date.today()
        next_order_date = get_next_order_date(today, input.frequency)
        # billing_address= cls.get_address(input.billing_address),
        # shipping_address= cls.get_address(input.shipping_address),

        subscription = Subscription(
            billing_address= billing_address,
            shipping_address= shipping_address,
            shipping_method_id=input.shipping_method_id,
            variant=variant,
            quantity=input.quantity,
            user=user,
            token_customer_id=input.token_customer_id,
            frequency=input.frequency,
            next_order_date=next_order_date
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

        address =  Address(
            first_name=first_name,
            last_name=last_name,
            company_name=company_name,
            street_address_1=street_address_1,
            street_address_2=street_address_2,
            city=city,
            city_area=city_area,
            postal_code=postal_code,
            country=country,
            country_area=country_area,
            phone=phone
        )
        address.save()
        return address

class SubscriptionCancel(graphene.Mutation):
    class Arguments:
        input = SubscriptionCancelInput(
            required = True,
            description="Fields required to cancel a Subscription."
        )
    subscription = graphene.Field(SubscriptionType)

    @classmethod
    def mutate(cls, root, info, input=None):
        user = info.context.user
        # get primary key from global id
        _, pk = from_global_id(input.subscription_id)
        # get the subscription using pk
        subscription = Subscription.objects.get(pk=pk)
        #update status of subscription to cancelled
        subscription.status = SubscriptionStatus.CANCELED
        # save the updated subscription object in the db
        subscription.save()
        # Notice we return an instance of this mutation
        return SubscriptionCancel(subscription=subscription)

class SubscriptionMutations(graphene.ObjectType):
    subscription_create = SubscriptionCreate.Field()
    subscription_cancel = SubscriptionCancel.Field()