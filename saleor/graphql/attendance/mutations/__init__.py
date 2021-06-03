from hmac import compare_digest
from datetime import datetime
import hmac, hashlib
from django.conf import settings

def sign(date):
    SECRET_KEY = settings.SECRET_KEY
    m = hmac.new(SECRET_KEY.encode(), digestmod=hashlib.sha256)
    m.update(date)
    m.hexdigest()
    return m.hexdigest().encode('utf-8')

def verify(hash):
    date = datetime.today().date()
    date = str(date).encode()
    good_sig = sign(date)
    return compare_digest(good_sig, hash.encode())