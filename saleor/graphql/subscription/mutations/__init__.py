from dateutil.relativedelta import relativedelta

def get_next_order_date(date, frequency):
    if frequency=="WEEKLY":
        delta = relativedelta(weeks=1)
    elif frequency=="MONTHLY":
        delta = relativedelta(months=1)

    next_date = date + delta

    return next_date