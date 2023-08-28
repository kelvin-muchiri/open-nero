import hashlib

from .twocheckout import Twocheckout

# pylint: skip-file


class Notification(Twocheckout):
    def __init__(self, dict_):
        super(self.__class__, self).__init__(dict_)

    @classmethod
    def check_hash(cls, params=None):
        m = hashlib.md5()  # nosec
        m.update(params["sale_id"].encode("utf-8"))
        m.update(params["vendor_id"].encode("utf-8"))
        m.update(params["invoice_id"].encode("utf-8"))
        m.update(params["secret"].encode("utf-8"))
        check_hash = m.hexdigest()
        check_hash = check_hash.upper()
        return check_hash == params["md5_hash"]

    @classmethod
    def check(cls, params=None):
        if params is None:
            params = {}
        if "sale_id" in params and "invoice_id" in params:
            check = Notification.check_hash(params)
            if check:
                response = {
                    "response_code": "SUCCESS",
                    "response_message": "Hash Matched",
                }
            else:
                response = {
                    "response_code": "FAILED",
                    "response_message": "Hash Mismatch",
                }
        else:
            response = {
                "response_code": "ERROR",
                "response_message": "You must pass sale_id, vendor_id, invoice_id, secret word.",
            }
        return cls(response)
