import os

from django.template.response import TemplateResponse
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.conf import settings
import requests
from urllib.parse import unquote
from .forms import ResetPassword
from saleor.account.models import User
import json
import hashlib
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
        # code to get email and first name from the body of the request
        email = body['user']['email']
        first_name = body['user']['givenName']

        secret = settings.SECRET_KEY
        # concatenate secret and email and generate a hash based on the concatenated string
        # use the hash as password
        base = secret+email
        base = base.encode()
        password = hashlib.sha224(base).hexdigest()

        #check wether a user with this email already exists
        user = User.objects.filter(email=email)
        # user does not exist create one
        if not user:
            response = register(email, password)
            # The response from server can be empty (in case of timeout)
            try:
                print("response.json(): {}".format(response.json()))
                # account created with no error
                if response.json()["data"]["accountRegister"]["accountErrors"]==[]:
                    #login 
                    response = login(email, password)
                    return_data = json.dumps(response)
                    token = response["data"]["tokenCreate"]["token"]
                    
                    #add first name to the account
                    response = add_first_name(first_name, token)
                    
                    # add account type social_auth in metadata
                    user = User.objects.filter(email=email)
                    account_data = {
                        'account_type' : 'social_auth'
                    }
                    user.store_value_in_metadata(account_data)

                    return HttpResponse(return_data, content_type='application/json')
                # error while registering new account
                else:
                    field = response.json()["data"]["accountRegister"]["accountErrors"][0]["field"]
                    message = response.json()["data"]["accountRegister"]["accountErrors"][0]["message"]
                    return_error = {
                        "data" : {
                            "tokenCreate" : {
                                "accountErrors" : {
                                    "field" : field,
                                    "message" : message
                                }
                            }
                        }
                    }
                    return_error = json.dumps(return_error)
                    return HttpResponse(return_error, content_type='application/json')
            # if the response from the server is empty then display error message
            except:
                print("json: : {}".format(json))
        # user already exists so just login
        else :
            response = login(email, password)
            return_data = json.dumps(response)
            return HttpResponse(return_data, content_type='application/json')

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