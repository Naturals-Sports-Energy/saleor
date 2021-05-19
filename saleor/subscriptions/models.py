from ..core.models import ModelWithMetadata
from django.db import models
from django.utils.timezone import now
from django.conf import settings
from ..account.models import Address
from ..shipping.models import ShippingMethod

from . import SubscriptionStatus, SubscriptionFrequency

class Subscription(ModelWithMetadata):
    created = models.DateTimeField(default=now, editable=False)
    status = models.CharField(
        max_length=32, default=SubscriptionStatus.ACTIVE, choices=SubscriptionStatus.CHOICES
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        blank=True,
        null=True,
        related_name="subscriptions",
        on_delete=models.SET_NULL,
    )

    billing_address = models.JSONField(default=None)
    shipping_address = models.JSONField(default=None)

    shipping_method_id = models.CharField(max_length=32)
    variant = models.ForeignKey(
        "product.ProductVariant",
        related_name="subscriptions",
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
    )
    quantity = models.IntegerField()

    token_customer_id = models.CharField(max_length=32, default=None)

    next_order_date = models.DateTimeField(default=now)

    frequency = models.CharField(
        max_length=255,
        choices=[
            (type_name.upper(), type_name) for type_name, _ in SubscriptionFrequency.CHOICES
        ],
    )
    


