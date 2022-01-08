from dateutil.relativedelta import relativedelta

def get_next_order_date(date, frequency_period, frequency_units):
    if frequency_period=="WEEKLY":
        delta = relativedelta(weeks=1)
    elif frequency_period=="MONTHLY":
        delta = relativedelta(months=1)

    next_date = date + (frequency_units*delta)

    return next_date