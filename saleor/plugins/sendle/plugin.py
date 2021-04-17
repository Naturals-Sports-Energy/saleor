from django.conf import settings
from urllib.parse import urljoin
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Union
from prices import Money, TaxedMoney, TaxedMoneyRange
from ...discount import DiscountInfo
from decimal import Decimal
import requests

from . import (
    DEFAULT_TAX_CODE,
    DEFAULT_TAX_DESCRIPTION,
    META_CODE_KEY,
    META_DESCRIPTION_KEY,
    SendleConfiguration,
    CustomerErrors,
    TransactionType,
    _validate_checkout,
    _validate_order,
    api_get_request,
    api_post_request,
    generate_request_data_from_checkout,
    get_api_url,
    get_country_name,
    get_cached_tax_codes_or_fetch,
    get_checkout_tax_data,
    get_order_request_data,
    get_order_tax_data,
)

from ..base_plugin import BasePlugin, ConfigurationTypeField

class SendlePlugin(BasePlugin):
    PLUGIN_ID = "plugin.sendleapi"  # plugin identifier
    PLUGIN_NAME = "Sendle API"  # display name of plugin
    PLUGIN_DESCRIPTION = "Deals with the logistics using Sendle API"
    DEFAULT_CONFIGURATION = [
        {"name": "Username", "value": None},
        {"name": "Password", "value": None},
        {"name": "Use sandbox", "value": True},
        {"name": "Pickup suburb", "value": 'North Strathfield'},
        {"name": "Pickup state-name", "value": 'NSW'},
        {"name": "Pickup postcode", "value": '2137'},
        {"name": "Pickup country", "value": 'AU'},        
    ]
    CONFIG_STRUCTURE = {
        "Username": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Provide username",
            "label": "Username",
        },
        "Password": {
            "type": ConfigurationTypeField.PASSWORD,
            "help_text": "Provide password",
            "label": "Password",
        },
        "Use sandbox": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": "Determines if Saleor should use Sendle sandbox API.",
            "label": "Use sandbox",
        },
        "Pickup suburb": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Provide the warehouse suburb. Suburb must be real and match pickup postcode.",
            "label": "Pickup suburb",
        },
        "Pickup state-name": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Must be the origin location’s state or territory. For Australia these are: ACT, NSW, NT, QLD, SA, TAS, VIC, WA, with the long-form (i.e. “Northern Territory”) also accepted. For United States these are the states 2 letter representation such as CA, NY.",
            "label": "Pickup state-name",
        },
        "Pickup postcode": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Provide warehouse postcode",
            "label": "Pickup postcode",
        },
        "Pickup country": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "ISO 3166 country code. Sendle currently supports AU for Australia and US for United States. If no pickup_country is provided this will default to AU.",
            "label": "Pickup country",
        },
    }
    DEFAULT_ACTIVE = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert to dict to easier take config elements
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.config = SendleConfiguration(
            username=configuration["Username"],
            password=configuration["Password"],
            use_sandbox=configuration["Use sandbox"],
            pickup_suburb=configuration["Pickup suburb"],
            pickup_state_name=configuration["Pickup state-name"],
            pickup_postcode=configuration["Pickup postcode"],
            pickup_country=configuration["Pickup country"],
        )


    def _skip_plugin(self, previous_value: Union[TaxedMoney, TaxedMoneyRange]) -> bool:
        if not self.active:
            return True

        # The previous plugin already calculated taxes so we can skip our logic
        if isinstance(previous_value, TaxedMoneyRange):
            start = previous_value.start
            stop = previous_value.stop

            return start.net != start.gross and stop.net != stop.gross

        if isinstance(previous_value, TaxedMoney):
            return previous_value.net != previous_value.gross
        return False

    def _calculate_checkout_shipping(
        self, 
        currency: str, 
        checkout:"Checkout", 
        lines: Iterable["CheckoutLine"], 
        shipping_price: TaxedMoney
    ) -> TaxedMoney:
        shipping_tax = Decimal(0.0)
        shipping_net = Decimal(0.0) #shipping_price.net.amount

        PARAMS = {
            'pickup_suburb': self.config.pickup_suburb,
            'pickup_postcode': self.config.pickup_postcode,
            'pickup_country' : self.config.pickup_country,
            'delivery_suburb' : checkout.shipping_address.city,
            'delivery_postcode' : checkout.shipping_address.postal_code,
            'delivery_country' : 'AU',
            'weight_value' : '0.0',
            'weight_units' : 'kg',
            'first_mile_option' : 'pickup'
        }

        AUTH = (
            self.config.username,
            self.config.password
        )

        HEADERS = {'Content-Type': 'application/json'}

        total_weight = 0
        for line in lines:
            weight = str.split(str(line.variant.weight))[0]
            total_weight += float(weight)

        PARAMS['weight_value'] = total_weight

        response = requests.get(
                url = urljoin(get_api_url(self.config.use_sandbox), 'quote'),
                params = PARAMS,
                headers = HEADERS,
                auth = AUTH
            )
        
        shipping_net = Decimal(response.json()[0]['quote']['net']['amount'])
        shipping_tax = Decimal(response.json()[0]['quote']['tax']['amount'])

        shipping_gross = Money(amount=shipping_net + shipping_tax, currency=currency)
        shipping_net = Money(amount=shipping_net, currency=currency)

        return TaxedMoney(net=shipping_net, gross=shipping_gross)

        # Alternate approach for calling quote api on every single product separately
        # for line in lines:
        #     weight = str.split(str(line.variant.weight))[0]
        #     PARAMS['weight_value'] =  float(weight)               #line.variant.weight.measurement
        #     response = requests.get(
        #         url = 'https://sandbox.sendle.com/api/quote',
        #         params = PARAMS,
        #         headers = HEADERS,
        #         auth = AUTH
        #     )
        #     shipping_net += Decimal(response.json()[0]['quote']['net']['amount'])
        #     shipping_tax += Decimal(response.json()[0]['quote']['tax']['amount'])           


        # shipping_gross = Money(amount=shipping_net + shipping_tax, currency=currency)
        # shipping_net = Money(amount=shipping_net, currency=currency)

        # return TaxedMoney(net=shipping_net, gross=shipping_gross)

    def calculate_checkout_shipping(
        self,
        checkout: "Checkout",
        lines: Iterable["CheckoutLine"],
        discounts: Iterable[DiscountInfo],
        previous_value: TaxedMoney,
    ) -> TaxedMoney:
        base_shipping_price = previous_value
        
        if self._skip_plugin(previous_value):
            return base_shipping_price

        if not _validate_checkout(checkout, lines):
            return base_shipping_price
        
        currency =  "AUD"                     #str(response.get("currencyCode"))
        return self._calculate_checkout_shipping(
            currency, checkout, lines, base_shipping_price
        )

    def order_fully_paid(
        self,
        order: "Order",
        previous_value: any
    ):
        DATA = {
            "weight": {
                "value":str.split(str(order.weight))[0],
                "units": "kg"
            },
            "first_mile_option": "pickup",
            "description": "sample description",
            "receiver": {
                "instructions": "sample instructions",
                "contact": {
                    "name" : 'customer',
                },
                "address": {
                    "address_line1": order.shipping_address.street_address_1,
                    "suburb": order.shipping_address.city,
                    "state_name": order.shipping_address.country_area,
                    "postcode": order.shipping_address.postal_code,
                    "country": "Australia"
                }
            },
            "sender": {
                "contact": {
                    "name": "Naturals"
                },
                "address": {
                    "address_line1": "Naturals Warehouse",
                    "suburb": self.config.pickup_suburb,
                    "state_name": self.config.pickup_state_name,
                    "postcode": self.config.pickup_postcode,
                    "country": get_country_name(self.config.pickup_country)
                }
            }
        }
        HEADERS = {'Content-Type': 'application/json','Idempotency-Key': str(order.id)}

        AUTH = (
            self.config.username,
            self.config.password
        )

        response = requests.post(
            url = urljoin(get_api_url(self.config.use_sandbox), 'orders'),
            headers = HEADERS,
            auth = AUTH,
            json = DATA
        )


