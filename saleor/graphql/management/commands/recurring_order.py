from operator import pos
from re import A
from django.core.management.base import BaseCommand, CommandError
from ....subscriptions.models import Subscription
from datetime import datetime
from ...api import schema
from freezegun import freeze_time
from . import create_draft_order, get_access_code,login,update_order_shipping,post_payment_form,check_payment_status
from ...subscription.mutations import get_next_order_date

class Command(BaseCommand):
    help = 'Closes the specified poll for voting'

    #@freeze_time("2021-06-20")
    def handle(self, *args, **options):
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


        self.stdout.write(self.style.SUCCESS('Successfully closed poll '))