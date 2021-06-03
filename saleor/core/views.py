import os
import logging

from django.template.response import TemplateResponse
from django.shortcuts import render
from django.http import HttpResponse, HttpResponseForbidden
from django.http import HttpResponseRedirect
from django.conf import settings
import requests
from urllib.parse import unquote
from .forms import ResetPassword
from saleor.account.models import User
import json
import hashlib
from apiclient import discovery
import httplib2
from oauth2client import client
from django.shortcuts import render
import qrcode
import qrcode.image.svg
from io import BytesIO
from ..graphql.attendance.mutations import sign
from datetime import datetime
from django.contrib.auth.decorators import login_required

logger = logging.getLogger(__name__)

GRAPHQL_URL = os.environ.get("GRAPHQL_URL", "http://0.0.0.0:8000/graphql/")

def home(request):
    storefront_url = os.environ.get("STOREFRONT_URL", "")
    dashboard_url = os.environ.get("DASHBOARD_URL", "")
    return TemplateResponse(
        request,
        "home/index.html",
        {"storefront_url": storefront_url, "dashboard_url": dashboard_url},
    )

def confirm_mail(request):
    GRAPHQL_URL = os.environ.get("GRAPHQL_URL", "http://0.0.0.0:8000/graphql/")
    email = unquote(request.GET.get('email'))
    token = request.GET.get('token')

    print("email:", email)
    query = """
    mutation confirmAccount($email:String!,$token:String!){
        confirmAccount(email:$email,token:$token){
            user{
            isActive
            }
            accountErrors{
            message
            }
        }
        }
    """
    URL = GRAPHQL_URL
    json = {
        "query": query,
        "variables": {
            "email": email,
            "token": token
        }
    }
    
    response = requests.post(url=URL, json=json)

    print("************************************************************")
    print("response:", response.json())
    if response.json()["data"]["confirmAccount"]["user"] is None:
        error = response.json()["data"]["confirmAccount"]["accountErrors"][0]["message"]
        message = error
        return TemplateResponse(
            request,
            "confirm_mail/fail.html",
            {"message":message},
        )
    else :
        print("response isActive= ", response.json()["data"]["confirmAccount"]["user"]["isActive"])
        message = "Email verified."
        return TemplateResponse(
            request,
            "confirm_mail/success.html",
            {"message":message},
        )
    

def forgot_password(request):
    if request.method == 'POST':
        form = ResetPassword(request.POST)
        new_password = form.data['new_password']
        confirm_new_password = form.data['confirm_new_password']
        email = form.data['email']
        token = form.data['token']
        
        GRAPHQL_URL = os.environ.get("GRAPHQL_URL", "http://0.0.0.0:8000/graphql/")

        print("new_password: {}".format(new_password))
        print("confirm_new_password: {}".format(confirm_new_password))
        if form.is_valid():
            print('email: {}'.format(email))
            print('password: {}'.format(token))

            query = """
            mutation setPassword($email:String!,$password:String!,$token:String!){
                setPassword(email:$email, password:$password, token:$token){
                    user{
                    email
                    isActive
                    }
                    accountErrors{
                        message
                    }
                }
            }
            """

            json = {
                "query" : query,
                "variables" : {
                    "email" : email,
                    "password" : new_password,
                    "token" : token
                }
            }
            URL = GRAPHQL_URL
            response = requests.post(url=URL, json=json)
            print("***********************************************")
            # The response from server can be empty (in case of timeout)
            try:
                print("response.json(): {}".format(response.json()))
                # check if there were any errors
                if response.json()["data"]["setPassword"]["accountErrors"]==[]:
                    return TemplateResponse(request, 'forgot_password/password_reset_success.html')
                # render reset fail page if there are errors and display error
                else:
                    error = response.json()["data"]["setPassword"]["accountErrors"][0]["message"]
                    return TemplateResponse(request, 'forgot_password/password_reset_fail.html', {'message': error})
            # if the response from the server is empty then display error message
            except:
                print("json: : {}".format(json))
            return TemplateResponse(request, 'forgot_password/password_reset_fail.html', {'message': 'Empty response from server.'})
    else:
        email = unquote(request.GET.get('email'))
        token = request.GET.get('token')
        form = ResetPassword(initial={"email":email,"token":token})

    return TemplateResponse(request, 'forgot_password/reset_password.html', {'form':form})

def sign_in_google(request):
    if request.method == 'POST':
        body = json.loads(request.body)
        print("social_auth body from front-end: {}".format(body))
        auth_code = body['userInfo']['serverAuthCode']
        print("auth_code: {}".format(auth_code))
        # If this request does not have `X-Requested-With` header, this could be a CSRF
        # if not request.headers.get('X-Requested-With'):
        #     return HttpResponseForbidden()

        # Set path to the Web application client_secret_*.json file you downloaded from the
        # Google API Console: https://console.developers.google.com/apis/credentials
        
        CLIENT_SECRET_FILE = './client_secret_536409948532-mmh90bq0eajc2m4huog2dlisn2ecp1f2.apps.googleusercontent.com.json'

        # Exchange auth code for access token, refresh token, and ID token
        credentials = client.credentials_from_clientsecrets_and_code(
            CLIENT_SECRET_FILE,
            ['https://www.googleapis.com/auth/drive.appdata', 'profile', 'email'],
            auth_code)

        # Call Google API
        http_auth = credentials.authorize(httplib2.Http())
        drive_service = discovery.build('drive', 'v3', http=http_auth)
        appfolder = drive_service.files().get(fileId='appfolder').execute()

        # Get profile info from ID token
        userid = credentials.id_token['sub']
        email = credentials.id_token['email']

        try:
            print("credential.access_token: {}".format(credentials.access_token))
            return_data = {
                'access_token' : credentials.access_token
            }
        except:
            return_data = {
                'access_token' : ''
            }


        return_data = json.dumps(return_data)
        return HttpResponse(return_data, content_type='application/json')

def access_token(request):
    if request.method == 'GET':
        # get query parameters
        print("request.GET: {}".format(request.GET))
        return HttpResponse()
    else:
        body = json.loads(request.body)
        print("access_token: {}".format(body))
        return HttpResponse()

def login(email, password):
    query = '''
    mutation loginUser($email: String!, $password: String!) {
        tokenCreate(email: $email, password: $password) {
        token
        refreshToken
        csrfToken
        user {
            id
            email
            firstName
            lastName
            addresses {
            id
            firstName
            lastName
            streetAddress1
            streetAddress2
            city
            postalCode
            isDefaultShippingAddress
            isDefaultBillingAddress
            phone
            countryArea
            country {
                country
            }
            }
            avatar {
            url
            alt
            }
        }
        accountErrors {
            field
            message
        }
        }
    }
    '''
    json = {
        "query" : query,
        "variables" : {
            "email" : email,
            "password" : password
        }
    }

    URL = GRAPHQL_URL
    response = requests.post(url=URL, json=json)
    response = response.json()

    return response

def register(email, password):
    query = '''
    mutation registerAccount($email:String!, $password:String!){
        accountRegister(input:{email:$email, password:$password}){
            requiresConfirmation
            accountErrors{
                message
                field
            }
            user{
                email
                isActive
            }
        }
    }
    '''
    json = {
        "query" : query,
        "variables" : {
            "email": email,
            "password": password
        }
    }
    URL = GRAPHQL_URL
    response = requests.post(url=URL, json=json)
    return response

def add_first_name(first_name, token):
    headers = {
        "Authorization" : "JWT {}".format(token)
    }
    
    query = '''
    mutation updateUser($input: AccountInput!) {
        accountUpdate(input: $input) {
            accountErrors {
                field
                message
            }
        }
    }
    '''
    json = {
        "query" : query,
        "variables" : {
            "input" : {
                "firstName" : first_name
            }
        }
    }

    URL = GRAPHQL_URL
    response = requests.post(url=URL, json=json, headers=headers)

    return response

def soap(request):
    customerId = unquote(request.GET.get('customerId'))
    username = unquote(request.GET.get('username'))
    password = unquote(request.GET.get('password'))

    url="https://www.eway.com.au/gateway/rebill/test/manageRebill_test.asmx"
    headers = {'content-type': 'text/xml'}
    body = """<?xml version="1.0" encoding="UTF-8"?>
            <soap:Envelope xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Header>
                <eWAYHeader xmlns="http://www.eway.com.au/gateway/rebill/manageRebill">
                    <eWAYCustomerID>{}</eWAYCustomerID>
                    <Username>{}</Username>
                    <Password>{}</Password>
                </eWAYHeader>
            </soap:Header>
             <soap:Body>
                <CreateRebillCustomer xmlns="http://www.eway.com.au/gateway/rebill/manageRebill">
                    <customerTitle>Mr</customerTitle>
                    <customerFirstName>Joe</customerFirstName>
                    <customerLastName>Bloggs</customerLastName>
                    <customerAddress>Bloggs Enterprise</customerAddress>
                    <customerSuburb>Capital City</customerSuburb>
                    <customerState>ACT</customerState>
                    <customerCompany>Bloggs</customerCompany>
                    <customerPostCode>2111</customerPostCode>
                    <customerCountry>Australia</customerCountry>
                    <customerEmail>test@eway.com.au</customerEmail>
                    <customerFax>0298989898</customerFax>
                    <customerPhone1>0297979797</customerPhone1>
                    <customerPhone2></customerPhone2>
                    <customerRef>Ref123</customerRef>
                    <customerJobDesc></customerJobDesc>
                    <customerComments>Please Ship ASASP</customerComments>
                    <customerURL>https://www.eway.com.au</customerURL>
                </CreateRebillCustomer>
            </soap:Body>
            </soap:Envelope>""".format(customerId, username, password)

    response = requests.post(url,data=body,headers=headers)
    print("**************************************************")
    print(response.content)

    return HttpResponse()

# @login_required
def qr_code(request):
    context = {}
    if request.method == "GET":
        token = unquote(request.GET.get('token'))
        logger.debug("token: %s", token)
        if authenticate(token):
            factory = qrcode.image.svg.SvgImage
            date = datetime.today().date()
            logger.debug("date: %s", date)
            hash = sign(date)
            logger.debug("hash: %s", hash)
            img = qrcode.make(hash, image_factory=factory, box_size=20)
            stream = BytesIO()
            img.save(stream)
            context["svg"] = stream.getvalue().decode()

            return render(request, 'qr_code.html', context=context)
        else:
            return HttpResponseForbidden()

def authenticate(token):
    headers = {
        "Authorization" : "JWT {}".format(token)
    }
    
    query = '''
    query me{
        me{
            isStaff
            isActive
        }
    }
    '''
    json = {
        "query" : query
    }

    URL = GRAPHQL_URL
    response = requests.post(url=URL, json=json, headers=headers)
    print(response)
    json_response = response.json()
    json_response = json_response["data"]["me"]
    print(json_response)
    logger.debug("isStaff: %s, isActive: %s",json_response.get("isStaff"),json_response.get("isActive") )
    if json_response.get("isStaff") and json_response.get("isActive"):
        return True

    return False