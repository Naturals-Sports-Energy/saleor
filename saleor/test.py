import sys
import requests
from typing import TYPE_CHECKING, Any, Dict, Iterable, List, Optional, Union
import logging
import json
from urllib.parse import urljoin

EWAY_USERNAME = os.environ.get("EWAY_USERNAME")
EWAY_PASSWORD = os.environ.get("EWAY_PASSWORD")
USE_SANDBOX = os.environ.get("USE_SANDBOX")
EWAY_URL = "https://api.sandbox.ewaypayments.com/"

if USE_SANDBOX:
    EWAY_URL = "https://api.sandbox.ewaypayments.com/"
else :
    EWAY_URL = "https://api.ewaypayments.com/"

logger = logging.getLogger(__name__)

try:
    URL = sys.argv[1]
except:
    URL = "http://0.0.0.0:8000/graphql/"

def graphql_query(url,query,variables,token=None):
    json = {
        "query": query,
        "variables": variables
    }

    try:
        if token:
            headers = {
                "Authorization" : "JWT {}".format(token)
            }
        response = requests.post(url=URL, json=json)
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

def api_post_request(
    url: str, headers: Dict[str, Any] = None, json: Dict[str, Any] = None, auth: (str,str) = None,data: Dict[str, Any] = None
) -> Dict[str, Any]:
    response = None
    json_response = None
    try:
        args = {
            'url':url,
        }
        if headers:
            args['headers'] = headers
        if json:
            args['json'] = json
        if data:
            args['data'] = data
        if auth:
            args['auth'] = auth

        response = requests.post(**args)
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

# login
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
  "email": "sognivurzo@biyac.com",
  "password": "password@123"
}

response = graphql_query(url=URL, query=query, variables=variables)
token = response["data"]["tokenCreate"]["token"]
customerId = response["data"]["tokenCreate"]["user"]["id"]
print("login complete. Token: {}".format(token))

# Create checkout object
query = """
    mutation CreateCheckoutObject($input: CheckoutCreateInput!){
	checkoutCreate(input:$input){
    checkoutErrors{
      field
      message
    }
    checkout{
      id
      token
      availablePaymentGateways{
        name
        id
        config{
          field
          value
        }
      }
      availableShippingMethods{
        id
        name
        price{
          amount
          currency
        }
      }
      shippingPrice{
        gross{
          amount
        }
      }
      subtotalPrice{
        gross{
          amount
        }
      }
      totalPrice{
        gross{
          amount
        }
      }
      lines{
        quantity
        variant{
          price{
            amount
          }
          costPrice{
            amount
          }
        }
        totalPrice{
          gross{
            amount
          }
        } 
      }
      shippingAddress{
        firstName
        streetAddress1
        country{
          code
        }
        countryArea
        city
        cityArea
        phone
        postalCode
      }
      isShippingRequired
    }
  }
}
"""

variables = {
  "input": {
    "lines": [
      {
        "quantity": 1,
        "variantId": "UHJvZHVjdFZhcmlhbnQ6MjAy"
      },
      {
        "quantity": 1,
        "variantId": "UHJvZHVjdFZhcmlhbnQ6MjA4"
      }
    ],
    "email": "admin@admin.com",
    "shippingAddress": {
      "firstName": "Kiran",
      "streetAddress1": "ghi",
      "country": "AU",
      "countryArea": "New South Wales",
      "city": "SYDNEY",
      "cityArea": "New South Wales",
      "phone": "+61291920995",
      "postalCode": "2000"
    },
    "billingAddress": {
      "firstName": "Kiran",
      "streetAddress1": "ghi",
      "country": "AU",
      "countryArea": "New South Wales",
      "city": "SYDNEY",
      "cityArea": "New South Wales",
      "phone": "+61291920995",
      "postalCode": "2000"
    }
    
  }
}

response = graphql_query(url=URL, query=query, variables=variables, token=token)
checkout_id = response["data"]["checkoutCreate"]["checkout"]["id"]
checkout_token = response["data"]["checkoutCreate"]["checkout"]["token"]

print("\ncheckout object created, checkout_id : {}, checkout_token: {}".format(checkout_id, checkout_token))

# Attach user to the checkout object
query = """
mutation attachCustomer($checkoutId:ID!,$customerId:ID!){
  checkoutCustomerAttach(checkoutId:$checkoutId,customerId:$customerId){
    checkoutErrors{
      message
    }
  }
}
"""

variables = {
  "checkoutId": checkout_id,
  "customerId": customerId
}

response = graphql_query(url=URL, query=query, variables=variables, token=token)


#update shipping method

query = """
mutation UpdateShippingMethod($checkoutId:ID!,$shippingMethodId:ID!){
  checkoutShippingMethodUpdate(
    checkoutId: $checkoutId
    shippingMethodId: $shippingMethodId
  ) {
    checkout {
      id
      metadata{
        key
        value
      }
      shippingPrice{
        net{
          amount
          currency
        }
        gross{
          amount
          currency
        }
      }
      lines{
        variant{
          name
          weight{
            value
            unit
          }
        }
        quantity
        totalPrice{
          gross{
            amount
          }
        }
      }
      shippingMethod {
        name
      }
      totalPrice {
        gross {
          amount
          currency
        }
      }
      subtotalPrice{
        gross{
          amount
        }
      }
    }
    checkoutErrors {
      field
      message
    }
  }
}
"""

variables = {
  "checkoutId" : checkout_id,
  "shippingMethodId" : "U2hpcHBpbmdNZXRob2Q6NQ=="
}

response = graphql_query(url=URL, query=query, variables=variables, token=token)

shipping_gross = response["data"]["checkoutShippingMethodUpdate"]["checkout"]["shippingPrice"]["gross"]["amount"]

print("\nShipping method updated, shipping price gross: {}".format(shipping_gross))

#Select Payment gateway

query = """
mutation SelectPayment($checkoutId: ID!, $input: PaymentInput!) {
  checkoutPaymentCreate(checkoutId: $checkoutId, input: $input) {
    checkout{
      token
      shippingPrice{
        gross{
          amount
          currency
        }
      }
      subtotalPrice{
        gross{
          amount
          currency
        }
      }
      totalPrice{
        gross{
          amount
          currency
        }
      }
    }
    payment {
      id
      chargeStatus
    }
    paymentErrors {
      field
      message
    }
  }
}
"""

variables = {
  "checkoutId": checkout_id,
  "input": {
    "gateway": "mirumee.payments.eway",
    "token": "3cb4993c-9075-405b-aa94-c44153be494c",
    "amount": 19.85,
    "billingAddress":  {
      "firstName": "Kiran",
      "streetAddress1": "ghi",
      "country": "AU",
      "countryArea": "New South Wales",
      "city": "SYDNEY",
      "phone": "+61291920995",
      "postalCode": "2000"
    }
  }
}

response = graphql_query(url=URL, query=query, variables=variables)

totalPrice = response["data"]["checkoutPaymentCreate"]["checkout"]["totalPrice"]["gross"]["amount"]
chargeStatus = response["data"]["checkoutPaymentCreate"]["payment"]["chargeStatus"]
checkout_token = response["data"]["checkoutPaymentCreate"]["checkout"]["token"]

print("\nPayment method selected, totalPrice: {}, chargeStatus: {}, checkout_token: {}".format(totalPrice, chargeStatus, checkout_token))

# Generating AccessCode from eway

totalPrice_inCents = int(totalPrice*100)
print("\ntotalPrice_inCents: {}".format(totalPrice_inCents))

InvoiceReference = checkout_id[:50] if len(checkout_id)>50 else checkout_id

data = {
    "Customer": {
        "Reference": "None",
        "Title": "Mr.",
        "FirstName": "Kiran",
        "LastName": "",
        "Street1": "ghi",
        "Street2": "",
        "City": "SYDNEY",
        "State": "NSW",
        "PostalCode": "2000",
        "Country": "au",
        "Phone": " 61291920995",
        "Email": "admin@admin.com",
    },
    "ShippingAddress": {
        "ShippingMethod": "Other",
        "FirstName": "Kiran",
        "LastName": "",
        "Street1": "ghi",
        "Street2": "",
        "City": "SYDNEY",
        "State": "NSW",
        "Country": "au",
        "PostalCode": "2000",
        "Phone": " 61291920995",
    },
    "Payment": {
        "TotalAmount": totalPrice_inCents,
        "InvoiceReference": InvoiceReference,
        "CurrencyCode": "AUD",
    },
    "RedirectUrl": "http://www.eway.com.au",
    "Method": "ProcessPayment",
    "TransactionType": "Purchase",
}

response = api_post_request(
    url= EWAY_URL+"AccessCodes",
    headers=None, json=data,
    auth=(EWAY_USERNAME,EWAY_PASSWORD)
)

AccessCode = response["AccessCode"]
FormActionURL = response["FormActionURL"]

print("\nAccessCode: {}".format(AccessCode))

# submitting card details form

url = FormActionURL
data = {
    "EWAY_ACCESSCODE" : AccessCode,
    "EWAY_PAYMENTTYPE":"Credit Card",
    "EWAY_CARDNAME" : "Hello",
    "EWAY_CARDNUMBER" : "4444333322221111",
    "EWAY_CARDEXPIRYMONTH" : "5",
    "EWAY_CARDEXPIRYYEAR" : "2023",
    "EWAY_CARDCVN" : "123"
}

response = requests.post(url=url, data=data)

print("\npayment prcoessing.")

# checkout complete

query = """
mutation completCheckout($checkoutId:ID!,$paymentData:JSONString){
  checkoutComplete(
    checkoutId: $checkoutId,
    paymentData: $paymentData
  ) {
    order {
      token
      metadata{
        key
        value
      }
      payments{
        creditCard{
          brand
          lastDigits
        }
      }
      id
      status
      isPaid
      weight{
        value
        unit
      }
      shippingPrice{
        gross{
          amount
          currency
        }
      }
      shippingMethod{
        name
      }
      subtotal{
        gross{
          amount
          currency
        }
      }
      total{
        gross{
          amount
          currency
        }
      }
    }
    checkoutErrors {
      field
      message
      code
    }
  }
}
"""
paymentData = {
    "AccessCode" : AccessCode
}

paymentData = json.dumps(paymentData)

variables = {
  "checkoutId" : checkout_id,
  "paymentData": paymentData
}

response = graphql_query(url=URL, query=query, variables=variables)

sendle_reference = ''
if response["data"]["checkoutComplete"]["order"] is None:
    print(response["data"]["checkoutComplete"]["checkoutErrors"][0]["message"])
    print("\nCheckout failed.")
else:
    order_id = response["data"]["checkoutComplete"]["order"]["id"]
    order_token = response["data"]["checkoutComplete"]["order"]["token"]
    order_isPaid = response["data"]["checkoutComplete"]["order"]["isPaid"]
    try:
      sendle_reference = response["data"]["checkoutComplete"]["order"]["metadata"][0]["value"]
    except Exception as e:
      logger.exception("{} , response: {}".format(e,response))

    print("\nCheckout complete, order_id : {}, order_token: {}, order_isPaid : {}, sendle_refernce: {}".format(order_id, order_token, order_isPaid,sendle_reference))

