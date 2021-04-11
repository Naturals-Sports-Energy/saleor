from typing import TYPE_CHECKING

from saleor.plugins.base_plugin import BasePlugin, ConfigurationTypeField

from ..utils import get_supported_currencies
from . import GatewayConfig, capture, process_payment, refund
from ... import TransactionKind
import base64

from ...interface import (
    GatewayConfig,
    GatewayResponse,
    InitializedPaymentResponse,
    PaymentData,
    PaymentGateway,
    PaymentMethodInfo
)

from . import (
    GatewayConfig,
    authorize,
    capture,
    confirm,
    get_client_token,
    process_payment,
    refund,
    void,
)

import requests

GATEWAY_NAME = "Eway"

def require_active_plugin(fn):
    def wrapped(self, *args, **kwargs):
        previous = kwargs.get("previous_value", None)
        if not self.active:
            return previous
        return fn(self, *args, **kwargs)

    return wrapped

class EwayGatewayPlugin(BasePlugin):
    PLUGIN_NAME = GATEWAY_NAME
    PLUGIN_ID = "mirumee.payments.eway"
    DEFAULT_ACTIVE = True
    DEFAULT_CONFIGURATION = [
        {"name": "username", "value": "F9802C65WIIJoC71srjdgq5kiMuTHDnRDK3ror9fXmZJzcH/LDTElbYEq0g22XW9cfEe+0"},
        {"name": "password", "value": "Fmv4KH8y"},
        {"name": "Store customers card", "value": False},
        {"name": "Automatic payment capture", "value": True},
        {"name": "Supported currencies", "value": ""},
    ]

    CONFIG_STRUCTURE = {
        "username": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Provide  username.",
            "label": "username",
        },
        "password": {
            "type": ConfigurationTypeField.SECRET,
            "help_text": "Provide password",
            "label": "password",
        },
        "Store customers card": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": "Determines if Saleor should store cards on payments "
            "in Stripe customer.",
            "label": "Store customers card",
        },
        "Automatic payment capture": {
            "type": ConfigurationTypeField.BOOLEAN,
            "help_text": "Determines if Saleor should automaticaly capture payments.",
            "label": "Automatic payment capture",
        },
        "Supported currencies": {
            "type": ConfigurationTypeField.STRING,
            "help_text": "Determines currencies supported by gateway."
            " Please enter currency codes separated by a comma.",
            "label": "Supported currencies",
        },
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        configuration = {item["name"]: item["value"] for item in self.configuration}
        self.config = GatewayConfig(
            gateway_name=GATEWAY_NAME,
            auto_capture=configuration["Automatic payment capture"],
            supported_currencies=configuration["Supported currencies"],
            connection_params={
                "username": configuration["username"],
                "password": configuration["password"]
            },
            store_customer=configuration["Store customers card"],
        )

    def _get_gateway_config(self):
        return self.config

    @require_active_plugin
    def authorize_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        with open('out.txt','a') as f:
            print("plugin auzthorize_payment",file =f)
        return authorize(payment_information, self._get_gateway_config())

    @require_active_plugin
    def capture_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return capture(payment_information, self._get_gateway_config())

    @require_active_plugin
    def confirm_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return confirm(payment_information, self._get_gateway_config())

    @require_active_plugin
    def refund_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return refund(payment_information, self._get_gateway_config())

    @require_active_plugin
    def void_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        return void(payment_information, self._get_gateway_config())

    @require_active_plugin
    def process_payment(
        self, payment_information: "PaymentData", previous_value
    ) -> "GatewayResponse":
        acces_code = payment_information.token
        print("eway access code: ", acces_code)
        USER = ('F9802C65WIIJoC71srjdgq5kiMuTHDnRDK3ror9fXmZJzcH/LDTElbYEq0g22XW9cfEe+0','Fmv4KH8y')
        URL = 'https://api.sandbox.ewaypayments.com/AccessCode/'+acces_code
        print("eway url: ", URL)
        response = requests.get(
            url=URL,
            auth=USER
        )
        print("*********************************\n Eway Response: ",response.json())

        status = response.json()['TransactionStatus']
        transaction_id = response.json()['TransactionID']

        return GatewayResponse(
            is_success = status,
            action_required = False,
            amount=payment_information.amount,
            currency=payment_information.currency,
            transaction_id=transaction_id,
            kind=TransactionKind.CAPTURE
        )
        # return process_payment(payment_information, self._get_gateway_config())

    @require_active_plugin
    def get_client_token(self, token_config: "TokenConfig", previous_value):
        return get_client_token()

    @require_active_plugin
    def get_supported_currencies(self, previous_value):
        config = self._get_gateway_config()
        return get_supported_currencies(config, GATEWAY_NAME)

    @require_active_plugin
    def get_payment_config(self, previous_value):
        config = self._get_gateway_config()
        sample_string = "{}:{}".format(config.connection_params["username"],config.connection_params["password"])
        sample_string_bytes = sample_string.encode("ascii")
        
        base64_bytes = base64.b64encode(sample_string_bytes)
        base64_string = base64_bytes.decode("ascii")
        base64_string = "BASIC "+base64_string
        return [{"field": "auth", "value": base64_string}]