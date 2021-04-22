import json
import logging
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Union
from urllib.parse import urljoin

import requests
from django.conf import settings
from django.contrib.sites.models import Site
from django.core.cache import cache
from requests.auth import HTTPBasicAuth

from ...checkout import base_calculations
from ...core.taxes import TaxError

if TYPE_CHECKING:
    # flake8: noqa
    from ...checkout.models import Checkout, CheckoutLine
    from ...order.models import Order
    from ...product.models import Product, ProductVariant, ProductType

logger = logging.getLogger(__name__)

META_CODE_KEY = "sendle.code"
META_DESCRIPTION_KEY = "sendle.description"
CACHE_TIME = 60 * 60  # 1 hour
TAX_CODES_CACHE_TIME = 60 * 60 * 24 * 7  # 7 days
CACHE_KEY = "sendle_request_id_"
TAX_CODES_CACHE_KEY = "avatax_tax_codes_cache_key"
TIMEOUT = 10  # API HTTP Requests Timeout

# Common carrier code used to identify the line as a shipping service
COMMON_CARRIER_CODE = "FR020100"

# Common discount code use to apply discount on order
COMMON_DISCOUNT_VOUCHER_CODE = "OD010000"

# Temporary Unmapped Other SKU - taxable default
DEFAULT_TAX_CODE = "O9999999"
DEFAULT_TAX_DESCRIPTION = "Unmapped Other SKU - taxable default"


@dataclass
class SendleConfiguration:
    username: str
    password: str
    use_sandbox: bool = True
    pickup_suburb: str = "DEFAULT"
    pickup_state_name: str = "DEFAULT"
    pickup_postcode: str = "DEFAULT"
    pickup_country: str = "DEFAULT"


class TransactionType:
    INVOICE = "SalesInvoice"
    ORDER = "SalesOrder"


class CustomerErrors:
    DEFAULT_MSG = "We are not able to calculate taxes for your order. Please try later"
    ERRORS = ("InvalidPostalCode", "InvalidAddress", "MissingAddress")

    @classmethod
    def get_error_msg(cls, error: dict) -> str:
        error_code = error.get("code")
        if error_code in cls.ERRORS:
            return error.get("message", cls.DEFAULT_MSG)
        return cls.DEFAULT_MSG


def get_api_url(use_sandbox=True) -> str:
    """Based on settings return sanbox or production url."""
    if use_sandbox:
        return "https://sandbox.sendle.com/api/"
    return "https://api.sendle.com/api/"

def api_post_request(
    url: str, headers: Dict[str, Any], data: Dict[str, Any], config: SendleConfiguration
) -> Dict[str, Any]:
    response = None
    try:
        auth = (config.username, config.password)
        response = requests.post(url, auth=auth, json=data, timeout=TIMEOUT)
        logger.debug("Hit to Sendle to get shipping price %s", url)
        json_response = response.json()
        if "error" in json_response:  # type: ignore
            error_message = json_response["error"]
            if "error_description" in json_response:
                error_message = error_message + ". " + json_response["error_description"]
            if "message" in json_response:
                error_message = error_message + ". " + json_response["message"]
            if "messages" in json_response:
                error_message = error_message + ". " + str(json_response["messages"])
            if "error_description" not in json_response and "message" not in json_response:
                error_message = error_message + "json response: " + json_response            
            logger.exception("Sendle response contains errors %s", error_message)
            return json_response
    except requests.exceptions.RequestException:
        logger.exception("Fetching shipping quotes failed %s", url)
        return {}
    except json.JSONDecodeError:
        content = response.content if response else "Unable to find the response"
        logger.exception(
            "Unable to decode the response from Sendle. Response: %s", content
        )
        return {}
    except :
        logger.exception(
            "Unexpected error. response_json: ".format(response.json())
        )
        return {}
    return json_response  # type: ignore


def api_get_request(
    url: str, params: Dict[str, Any], headers: Dict[str, Any], config: SendleConfiguration
) -> Dict[str, Any]:
    response = None
    try:
        auth = HTTPBasicAuth(config.username, config.password)
        response = requests.get(url, params=params, auth=auth, timeout=TIMEOUT)
        json_response = response.json()
        logger.debug("[GET] Hit to %s", url)
        if "error" in json_response:  # type: ignore
            logger.error("Avatax response contains errors %s", json_response)
        return json_response
    except requests.exceptions.RequestException:
        logger.exception("Failed to fetch data from %s", url)
        return {}
    except json.JSONDecodeError:
        content = response.content if response else "Unable to find the response"
        logger.exception(
            "Unable to decode the response from Avatax. Response: %s", content
        )
        return {}

def get_country_name(country_code='AU') -> str:
    if country_code=='AU':
        return 'Australia'
    elif country_code=='US':
        return 'United States'


def _validate_adddress_details(
    shipping_address, is_shipping_required, address, shipping_method
):
    if not is_shipping_required and address:
        return True
    if not shipping_address:
        return False
    if not shipping_method:
        return False
    return True


def _validate_order(order: "Order") -> bool:
    """Validate the order object if it is ready to generate a request to avatax."""
    if not order.lines.exists():
        return False
    shipping_address = order.shipping_address
    is_shipping_required = order.is_shipping_required()
    address = shipping_address or order.billing_address
    return _validate_adddress_details(
        shipping_address, is_shipping_required, address, order.shipping_method
    )


def _validate_checkout(checkout: "Checkout", lines: Iterable["CheckoutLine"]) -> bool:
    """Validate the checkout object if it is ready to generate a request to avatax."""
    if not lines:
        return False

    shipping_address = checkout.shipping_address
    is_shipping_required = checkout.is_shipping_required()
    address = shipping_address or checkout.billing_address
    return _validate_adddress_details(
        shipping_address, is_shipping_required, address, checkout.shipping_method
    )


def _retrieve_from_cache(token):
    taxes_cache_key = CACHE_KEY + token
    cached_data = cache.get(taxes_cache_key)
    return cached_data


def taxes_need_new_fetch(data: Dict[str, Any], taxes_token: str) -> bool:
    """Check if Avatax's taxes data need to be refetched.

    The response from Avatax is stored in a cache. If an object doesn't exist in cache
    or something has changed, taxes need to be refetched.
    """
    cached_data = _retrieve_from_cache(taxes_token)

    if not cached_data:
        return True

    cached_request_data, _ = cached_data
    if data != cached_request_data:
        return True
    return False


def append_line_to_data(
    data: List[Dict[str, Union[str, int, bool, None]]],
    quantity: int,
    amount: Decimal,
    tax_code: str,
    item_code: str,
    name: str = None,
    tax_included: Optional[bool] = None,
):
    if tax_included is None:
        tax_included = Site.objects.get_current().settings.include_taxes_in_prices
    data.append(
        {
            "quantity": quantity,
            "amount": str(amount),
            "taxCode": tax_code,
            "taxIncluded": tax_included,
            "itemCode": item_code,
            "description": name,
        }
    )


def append_shipping_to_data(data: List[Dict], shipping_method):
    charge_taxes_on_shipping = (
        Site.objects.get_current().settings.charge_taxes_on_shipping
    )
    if charge_taxes_on_shipping and shipping_method:
        append_line_to_data(
            data,
            quantity=1,
            amount=shipping_method.price.amount,
            tax_code=COMMON_CARRIER_CODE,
            item_code="Shipping",
        )


def get_checkout_lines_data(
    checkout: "Checkout", discounts=None
) -> List[Dict[str, Union[str, int, bool, None]]]:
    data: List[Dict[str, Union[str, int, bool, None]]] = []
    lines = checkout.lines.prefetch_related(
        "variant__product__category",
        "variant__product__collections",
        "variant__product__product_type",
    ).filter(variant__product__charge_taxes=True)
    for line in lines:
        name = line.variant.product.name
        product = line.variant.product
        product_type = line.variant.product.product_type
        tax_code = retrieve_tax_code_from_meta(product, default=None)
        tax_code = tax_code or retrieve_tax_code_from_meta(product_type)
        append_line_to_data(
            data=data,
            quantity=line.quantity,
            amount=base_calculations.base_checkout_line_total(
                line, discounts
            ).gross.amount,
            tax_code=tax_code,
            item_code=line.variant.sku,
            name=name,
        )

    append_shipping_to_data(data, checkout.shipping_method)
    return data


def get_order_lines_data(
    order: "Order",
) -> List[Dict[str, Union[str, int, bool, None]]]:
    data: List[Dict[str, Union[str, int, bool, None]]] = []
    lines = order.lines.prefetch_related(
        "variant__product__category",
        "variant__product__collections",
        "variant__product__product_type",
    ).filter(variant__product__charge_taxes=True)
    system_tax_included = Site.objects.get_current().settings.include_taxes_in_prices
    for line in lines:
        if not line.variant:
            continue
        product = line.variant.product
        product_type = line.variant.product.product_type
        tax_code = retrieve_tax_code_from_meta(product, default=None)
        tax_code = tax_code or retrieve_tax_code_from_meta(product_type)

        # Confirm if line doesn't have included taxes in the price. If not then, we
        # check if the current Saleor config doesn't assume that taxes are included in
        # prices
        line_has_included_taxes = (
            line.unit_price_gross_amount != line.unit_price_net_amount
        )
        tax_included = line_has_included_taxes or system_tax_included

        append_line_to_data(
            data=data,
            quantity=line.quantity,
            amount=line.unit_price_gross_amount * line.quantity,
            tax_code=tax_code,
            item_code=line.variant.sku,
            name=line.variant.product.name,
            tax_included=tax_included,
        )
    if order.discount_amount:
        append_line_to_data(
            data=data,
            quantity=1,
            amount=order.discount_amount * -1,
            tax_code=COMMON_DISCOUNT_VOUCHER_CODE,
            item_code="Voucher",
            name=order.discount_name,
            tax_included=True,  # Voucher should be always applied as a gross amount
        )
    append_shipping_to_data(data, order.shipping_method)
    return data


def generate_request_data(
    transaction_type: str,
    lines: List[Dict[str, Any]],
    transaction_token: str,
    address: Dict[str, str],
    customer_email: str,
    config: SendleConfiguration,
    currency=settings.DEFAULT_CURRENCY,
):
    company_address = Site.objects.get_current().settings.company_address
    if company_address:
        company_address = company_address.as_data()
    else:
        logging.warning(
            "To correct calculate taxes by Avatax, company address should be provided "
            "in dashboard.settings."
        )
        company_address = {}

    data = {
        "companyCode": config.company_name,
        "type": transaction_type,
        "lines": lines,
        "code": transaction_token,
        "date": str(date.today()),
        # https://developer.avalara.com/avatax/dev-guide/transactions/simple-transaction/
        "customerCode": 0,
        "addresses": {
            "shipFrom": {
                "line1": company_address.get("street_address_1"),
                "line2": company_address.get("street_address_2"),
                "city": company_address.get("city"),
                "region": company_address.get("country_area"),
                "country": company_address.get("country"),
                "postalCode": company_address.get("postal_code"),
            },
            "shipTo": {
                "line1": address.get("street_address_1"),
                "line2": address.get("street_address_2"),
                "city": address.get("city"),
                "region": address.get("country_area"),
                "country": address.get("country"),
                "postalCode": address.get("postal_code"),
            },
        },
        "commit": config.autocommit,
        "currencyCode": currency,
        "email": customer_email,
    }
    return {"createTransactionModel": data}


def generate_request_data_from_checkout(
    checkout: "Checkout",
    config: SendleConfiguration,
    transaction_token=None,
    transaction_type=TransactionType.ORDER,
    discounts=None,
):

    address = checkout.shipping_address or checkout.billing_address
    lines = get_checkout_lines_data(checkout, discounts)

    currency = checkout.currency
    data = generate_request_data(
        transaction_type=transaction_type,
        lines=lines,
        transaction_token=transaction_token or str(checkout.token),
        address=address.as_data() if address else {},
        customer_email=checkout.email,
        config=config,
        currency=currency,
    )
    return data


def _fetch_new_taxes_data(
    data: Dict[str, Dict], data_cache_key: str, config: SendleConfiguration
):
    transaction_url = urljoin(
        get_api_url(config.use_sandbox), "transactions/createoradjust"
    )
    response = api_post_request(transaction_url, data, config)
    if response and "error" not in response:
        cache.set(data_cache_key, (data, response), CACHE_TIME)
    else:
        # cache failed response to limit hits to avatax.
        cache.set(data_cache_key, (data, response), 10)
    return response


def get_cached_response_or_fetch(
    data: Dict[str, Dict],
    token_in_cache: str,
    config: SendleConfiguration,
    force_refresh: bool = False,
):
    """Try to find response in cache.

    Return cached response if requests data are the same. Fetch new data in other cases.
    """
    data_cache_key = CACHE_KEY + token_in_cache
    if taxes_need_new_fetch(data, token_in_cache) or force_refresh:
        response = _fetch_new_taxes_data(data, data_cache_key, config)
    else:
        _, response = cache.get(data_cache_key)

    return response


def get_checkout_tax_data(
    checkout: "Checkout", discounts, config: SendleConfiguration
) -> Dict[str, Any]:
    data = generate_request_data_from_checkout(checkout, config, discounts=discounts)
    return get_cached_response_or_fetch(data, str(checkout.token), config)


def get_order_request_data(order: "Order", config: SendleConfiguration):
    address = order.shipping_address or order.billing_address
    lines = get_order_lines_data(order)
    transaction = (
        TransactionType.INVOICE if not order.is_draft() else TransactionType.ORDER
    )
    data = generate_request_data(
        transaction_type=transaction,
        lines=lines,
        transaction_token=order.token,
        address=address.as_data() if address else {},
        customer_email=order.user_email,
        config=config,
        currency=order.total.currency,
    )
    return data


def get_order_tax_data(
    order: "Order", config: SendleConfiguration, force_refresh=False
) -> Dict[str, Any]:
    data = get_order_request_data(order, config)
    response = get_cached_response_or_fetch(
        data, "order_%s" % order.token, config, force_refresh
    )
    error = response.get("error")
    if error:
        raise TaxError(error)
    return response


def generate_tax_codes_dict(response: Dict[str, Any]) -> Dict[str, str]:
    tax_codes = {}
    for line in response.get("value", []):
        if line.get("isActive"):
            tax_codes[line.get("taxCode")] = line.get("description")
    return tax_codes


def get_cached_tax_codes_or_fetch(
    config: SendleConfiguration, cache_time: int = TAX_CODES_CACHE_TIME
):
    """Try to get cached tax codes.

    If the cache is empty, fetch the newest taxcodes from avatax.
    """
    tax_codes = cache.get(TAX_CODES_CACHE_KEY, {})
    if not tax_codes:
        tax_codes_url = urljoin(get_api_url(config.use_sandbox), "definitions/taxcodes")
        response = api_get_request(
            tax_codes_url, config.username_or_account, config.password_or_license
        )
        if response and "error" not in response:
            tax_codes = generate_tax_codes_dict(response)
            cache.set(TAX_CODES_CACHE_KEY, tax_codes, cache_time)
    return tax_codes


def retrieve_tax_code_from_meta(
    obj: Union["Product", "ProductVariant", "ProductType"],
    default: Optional[str] = DEFAULT_TAX_CODE,
):
    tax_code = obj.get_value_from_metadata(META_CODE_KEY, default)
    return tax_code
