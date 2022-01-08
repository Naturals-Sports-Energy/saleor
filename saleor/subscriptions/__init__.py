class SubscriptionStatus:
    ACTIVE = "active" # subscirption is active
    CANCELED = "canceled"  # permanently canceled subscription

    CHOICES = [
        (ACTIVE, "Active"),
        (CANCELED, "Canceled"),
    ]

class SubscriptionFrequency:
    MONTHLY="MONTHLY" # monthly subscription
    WEEKLY="WEEKLY" # weekly subscription
 
    CHOICES = [
        (MONTHLY,"MONTHLY"),
        (WEEKLY,"WEEKLY"),
    ]