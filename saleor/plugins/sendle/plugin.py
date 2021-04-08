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
        {"name": "Username or account", "value": None},
        {"name": "Password or license", "value": None},
        {"name": "Use sandbox", "value": True},
        {"name": "Company name", "value": "DEFAULT"},
        {"name": "Autocommit", "value": False},
    ]
    CONFIG_STRUCTURE = {
        "Username or account": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Provide user or account details",
            "label": "Username or account",
        },
        "Password or license": {
            "type": ConfigurationTypeField.PASSWORD,
            "help_text": "Provide password or license details",
            "label": "Password or license",
        },
        "Use sandbox": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": "Determines if Saleor should use Avatax sandbox API.",
            "label": "Use sandbox",
        },
        "Company name": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Avalara needs to receive company code. Some more "
            "complicated systems can use more than one company "
            "code, in that case, this variable should be changed "
            "based on data from Avalara's admin panel",
            "label": "Company name",
        },
        "Autocommit": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": "Determines, if all transactions sent to Avalara "
            "should be committed by default.",
            "label": "Autocommit",
        },
    }
    DEFAULT_ACTIVE = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Convert to dict to easier take config elements
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.config = SendleConfiguration(
            username_or_account=configuration["Username or account"],
            password_or_license=configuration["Password or license"],
            use_sandbox=configuration["Use sandbox"],
            company_name=configuration["Company name"],
            autocommit=configuration["Autocommit"],
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

        print("\n\n\n\n\n city_area:",checkout.shipping_address.city_area)
        print("post_code:",checkout.shipping_address.postal_code)
        PARAMS = {
            'pickup_suburb': 'North Strathfield',
            'pickup_postcode': '2137',
            'pickup_country' : 'AU',
            'delivery_suburb' : checkout.shipping_address.city,
            'delivery_postcode' : checkout.shipping_address.postal_code,
            'delivery_country' : 'AU',
            'weight_value' : '0.0',
            'weight_units' : 'kg',
            'first_mile_option' : 'pickup'
        }

        AUTH = (
            'sujeeshsvalath_gmail',
            '6bWNSdTGHYBdFRqvXWD3T8bD'
        )

        HEADERS = {'Content-Type': 'application/json'}

        total_weight = 0
        for line in lines:
            weight = str.split(str(line.variant.weight))[0]
            total_weight += float(weight)

        PARAMS['weight_value'] = total_weight

        response = requests.get(
                url = 'https://sandbox.sendle.com/api/quote',
                params = PARAMS,
                headers = HEADERS,
                auth = AUTH
            )
        print("\n\n\n\n\n\nresponse= ",response.json())
        
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
            print("skip_plugin")
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
                    "suburb": "North Strathfield",
                    "state_name": "NSW",
                    "postcode": "2137",
                    "country": "Australia"
                }
            }
        }
        HEADERS = {'Content-Type': 'application/json','Idempotency-Key': str(order.id)}

        AUTH = (
            'sujeeshsvalath_gmail',
            '6bWNSdTGHYBdFRqvXWD3T8bD'
        )
        response = requests.post(
            url = "https://sandbox.sendle.com/api/orders",
            headers = HEADERS,
            auth = AUTH,
            json = DATA
        )

        # print("\n\n\n\nresponse: ",response.json())


