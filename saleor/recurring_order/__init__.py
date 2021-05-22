from dis import dis
from re import sub
from django.db.models.aggregates import Variance
from django.http import response

from requests.api import head
from saleor import discount, order
import graphene
import json
import requests
import os
from urllib.parse import urljoin
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Union
import logging
from ..discount.models import Voucher

logger = logging.getLogger(__name__)

URL = os.environ.get("GRAPHQL_URL", "http://0.0.0.0:8000/graphql/")
EMAIL = os.environ.get("USERNAME")
PASSWORD = os.environ.get("PASSWORD")
EWAY_USERNAME = os.environ.get("EWAY_USERNAME")
EWAY_PASSWORD = os.environ.get("EWAY_PASSWORD")

def login():
    query = """
        mutation login($email:String!,$password:String!){
            tokenCreate(email:$email, password:$password){
                token
                user{
                id
                }
            }
        }
    """

    variables = {
    "email": EMAIL,
    "password": PASSWORD
    }

    response = graphql_query(url=URL, query=query, variables=variables)
    token = response["data"]["tokenCreate"]["token"]
    customerId = response["data"]["tokenCreate"]["user"]["id"]
    
    return token

def api_post_request(url, json, auth):
    response = None
    json_response = None
    try:
        response = requests.post(url=url,json=json, auth=auth)
        logger.debug("Hit API %s", url)
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
        logger.exception("Fetching failed %s", url)
        return {}
    except json.JSONDecodeError:
        content = response.content if response else "Unable to find the response"
        logger.exception(
            "Unable to decode the response. Response: %s", content
        )
        return {}
    except :
        logger.exception(
            "Unexpected error. response_json: ".format(response.json())
        )
        return {}
    return json_response  # type: ignore

def graphql_query(url,query,variables,token=None):
    json = {
        "query": query,
        "variables": variables
    }
    headers=None
    try:
        if token:
            headers = {
                "Authorization" : "JWT {}".format(token)
            }
        response = requests.post(url=URL, json=json, headers=headers)
        json_response = response.json()
        if "error" in response:  # type: ignore
            print("Graphql response contains errors %s", json_response)
            return json_response
    except requests.exceptions.RequestException:
        print("Fetching query result failed %s", url)
        return {}
    except json.JSONDecodeError:
        content = response.content if response else "Unable to find the response"
        print(
            "Unable to decode the response from graphql. Response: %s", content
        )
        return {}
    return json_response  # type: ignore

def create_draft_order(subscription, token):
    query = """
        mutation createDraftOrder($input:DraftOrderCreateInput!){
            draftOrderCreate(input:$input){
                orderErrors{
                    field
                    message
                }
                order{
                    id
                    token
                    status
                    isPaid
                    paymentStatusDisplay
                    shippingPrice{
                        gross{
                            amount
                        }
                    }
                    total{
                        gross{
                            amount
                        }
                    }
                }
            }
        }
    """
    billing_address = subscription.billing_address
    shipping_address = subscription.shipping_address

    price = float(subscription.variant.price.amount)
    print("price: {}".format(price))
    
    # apply 20% instant discount
    # discount = (price*0.2)*subscription.quantity

    # apply 20% off voucher
    voucher = os.environ.get("RECURRING_20_OFF")
    voucher_local_id = Voucher.objects.filter(code=voucher).first().id
    voucher_global_id = graphene.Node.to_global_id("Voucher", voucher_local_id)
    
    variables = {
        "input": {
            "billingAddress": {
                "firstName": billing_address.first_name,
                "lastName": billing_address.last_name or "lastName",
                "companyName": billing_address.company_name or "companyName",
                "streetAddress1": billing_address.street_address_1,
                "streetAddress2": billing_address.street_address_2 or "address2",
                "city": billing_address.city,
                "cityArea": billing_address.city_area,
                "postalCode": billing_address.postal_code,
                "country": billing_address.country.code,
                "countryArea": billing_address.country_area,
                "phone": "+"+str(billing_address.phone.country_code)+str(billing_address.phone.national_number)
            },
            "shippingAddress": {
                "firstName": shipping_address.first_name,
                "lastName": shipping_address.last_name,
                "companyName": shipping_address.company_name,
                "streetAddress1": shipping_address.street_address_1,
                "streetAddress2": shipping_address.street_address_2,
                "city": shipping_address.city,
                "cityArea": shipping_address.city_area,
                "postalCode": shipping_address.postal_code,
                "country": shipping_address.country.code,
                "countryArea": shipping_address.country_area,
                "phone": "+"+str(shipping_address.phone.country_code)+str(shipping_address.phone.national_number)
            },
            "shippingMethod": subscription.shipping_method_id,
            "lines": [{
                "quantity": subscription.quantity,
                "variantId": graphene.Node.to_global_id("ProductVariant", subscription.variant.id) 
            }],
            "voucher": voucher_global_id,
            "user": graphene.Node.to_global_id("User", subscription.user.id)
        }
    }
    response = graphql_query(url=URL, query=query, variables=variables, token=token)
    try:
        response = response["data"]["draftOrderCreate"]["order"]
    except:
        error_message=""
        if "error" in response:  # type: ignore
            error_message = response["error"]
            if "error_description" in response:
                error_message = error_message + ". " + response["error_description"]
            if "message" in response:
                error_message = error_message + ". " + response["message"]
            if "messages" in response:
                error_message = error_message + ". " + str(response["messages"])
            if "error_description" not in response and "message" not in response:
                error_message = error_message + "json response: " + response            
        print("Sendle response contains errors {}".format(response))

    return response

def update_order_shipping(order_id , shippingMethod, token):
    # order_id = graphene.Node.to_global_id("Order", order_id)
    query = """
    mutation updateShipping($order:ID!, $input:OrderUpdateShippingInput){
        orderUpdateShipping(order:$order, input:$input){
            order{
                total{
                    gross{
                        amount
                    }
                }
            }
        }
    }
    """
    variables = {
        "order": order_id,
        "input": {
            "shippingMethod": shippingMethod
        }
    }

    response = graphql_query(url=URL, query=query, variables=variables, token=token)
    total_price = response["data"]["orderUpdateShipping"]["order"]["total"]["gross"]["amount"]
    return total_price

def get_access_code(subscription, total_price):
    user = subscription.user
    billing_address = subscription.billing_address
    shipping_address = subscription.shipping_address

    data = {
        "Customer": {
            "Title": "",
            "TokenCustomerID": subscription.token_customer_id,
            "FirstName": user.first_name,
            "LastName": user.last_name,
            "Street1": billing_address.street_address_1,
            "City": billing_address.city,
            "State": billing_address.city_area,
            "PostalCode": billing_address.postal_code,
            "Country": shipping_address.country.code,
            "Phone": "+"+str(shipping_address.phone.country_code)+str(shipping_address.phone.national_number),
            "Email": user.email,
        },
        "ShippingAddress": {
            "ShippingMethod": "Other",
            "FirstName": shipping_address.first_name,
            "LastName": shipping_address.last_name,
            "Country": shipping_address.country.code,
        },
        "Payment": {
            "TotalAmount": total_price,
            # "InvoiceReference": InvoiceReference,
            "CurrencyCode": "AUD",
        },
        "RedirectUrl": "http://www.eway.com.au",
        "Method": "TokenPayment",
        "TransactionType": "Recurring"
    }
    response = api_post_request(
        url="https://api.sandbox.ewaypayments.com/AccessCodes",
        json=data,
        auth=(EWAY_USERNAME, EWAY_PASSWORD)
    )

    AccessCode = response["AccessCode"]
    FormActionURL = response["FormActionURL"]

    return {
        "AccessCode" : AccessCode,
        "FormActionURL" : FormActionURL
    }

def post_payment_form(AccessCode, FormActionURL):
    url = FormActionURL
    data = {
        "EWAY_ACCESSCODE" : AccessCode,
    }
    response = requests.post(url=url, data=data)

def check_payment_status(AccessCode, order_token, order_id, token):
    USER = (
        EWAY_USERNAME,
        EWAY_PASSWORD
    )
    URL = urljoin(urljoin("https://api.sandbox.ewaypayments.com/",'AccessCode/'),AccessCode)
    response = requests.get(
        url=URL,
        auth=USER
    )
    # In case the auth is None then the response will be empty and response.json() will raise exception
    try:
        data = response.json()
    except:
        data = {}

    # if the response is empty(No TransactionID) then use payment_information.token as transaction_id
    transaction_id = data.get("TransactionID", order_token)
    # if the response is not empty and contains TransactionID but the value is None then use payment_information.token
    if transaction_id is None:
        transaction_id = order_token

    is_success = data.get("TransactionStatus",False)
    
    if is_success:
        if order_mark_paid(order_id, token):
            draft_order_complete(order_id, token)
            return True
    
    return False


def order_mark_paid(order_id, token):
    query = """
    mutation markPaid($id:ID!){
        orderMarkAsPaid(id:$id){
            order{
                isPaid
            }
        }
    }
    """
    variables = {
        "id": order_id
    }

    response = graphql_query(url=URL, query=query, variables=variables, token=token)
    is_paid = response["data"]["orderMarkAsPaid"]["order"]["isPaid"]

    return is_paid

def draft_order_complete(order_id, token):
    query = """
    mutation completeDraftOrder($id: ID!){
        draftOrderComplete(id:$id){
            order{
                id
                statusDisplay
            }
        }
    }
    """

    variables = {
        "id" : order_id,
    }

    response = graphql_query(url=URL, query=query, variables=variables, token=token)
    if response["data"]:
        print("draft order complete")
        return True
    else:
        return False

    