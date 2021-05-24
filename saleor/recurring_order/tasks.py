from celery.schedules import crontab
from ..celeryconf import app
from celery.utils.log import get_task_logger
from ..subscriptions.models import Subscription
from datetime import datetime
from ..graphql.subscription.mutations import get_next_order_date
import graphene
import requests
import os
from urllib.parse import urljoin
from typing import TYPE_CHECKING, Any, Dict,List
import logging
from saleor.discount.models import Voucher

logger = logging.getLogger(__name__)

URL = os.environ.get("GRAPHQL_URL", "http://0.0.0.0:8000/graphql/")
EMAIL = os.environ.get("USERNAME")
PASSWORD = os.environ.get("PASSWORD")
EWAY_USERNAME = os.environ.get("EWAY_USERNAME")
EWAY_PASSWORD = os.environ.get("EWAY_PASSWORD")

logger = get_task_logger(__name__)


@app.on_after_finalize.connect
def setup_periodic_tasks(sender, **kwargs):
    # Execute daily at midnight.
    sender.add_periodic_task(
        crontab(minute=0, hour=0),
        recurring_order.s(),
    )

@app.task
def test(arg):
    print(arg)

@app.task
def recurring_order():
    # get active subscriptions from database 
    subscriptions = Subscription.objects.filter(status="active").filter(next_order_date=datetime.today().date())
    print(subscriptions)

    orders = {}

    #admin login to get token
    token = login()
    
    # create draftOrders for each of the subscriptions
    for subscription in subscriptions:
        order = create_draft_order(subscription,token)
        orders[subscription.id] = {}
        orders[subscription.id]["order_id"] = order["id"]
        orders[subscription.id]["order_token"] = order["token"]
        total_price = update_order_shipping(order["id"], subscription.shipping_method_id, token)
        totalPrice_inCents = int(total_price*100)
        orders[subscription.id]["total_price"] = totalPrice_inCents

    print(orders)

    # generate access code for each subscription

    for subscription in subscriptions:
        total_price = orders[subscription.id]["total_price"]
        response = get_access_code(subscription, total_price)
        orders[subscription.id]["AccessCode"] = response["AccessCode"]
        orders[subscription.id]["FormActionURL"] = response["FormActionURL"]
        

    #post payment details form

    for subscription in subscriptions:
        AccessCode = orders[subscription.id]["AccessCode"]
        FormActionURL = orders[subscription.id]["FormActionURL"]
        post_payment_form(AccessCode, FormActionURL)


    #check payment status and place order if paid 
    for subscription in subscriptions:
        AccessCode = orders[subscription.id]["AccessCode"]
        order_token = orders[subscription.id]["order_token"]
        order_id = orders[subscription.id]["order_id"]
        if check_payment_status(AccessCode, order_token, order_id, token):
            #update next_order_date
            subscription.next_order_date = get_next_order_date(
                subscription.next_order_date, 
                subscription.frequency
            )
            subscription.save()


    logger.info("Successfully Placed Recurring Orders.")

# Helper Functions

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
    
    try:
        token = response["data"]["tokenCreate"]["token"]
    except:
        print("login faild, response: {}".format(response))
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
    except requests.exceptions.RequestException as e:
        print("Fetching query result failed, url: {}".format(url))
        print("json: {}, headers: {}, exception: {}".format(json, headers, e))
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
    try:    
        is_paid = response["data"]["orderMarkAsPaid"]["order"]["isPaid"]
    except Exception as e:
        print("could not mark as paid")
        print("response: {}, exception: {}".format(response,e))

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