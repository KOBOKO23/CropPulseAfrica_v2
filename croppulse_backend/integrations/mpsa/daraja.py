# M-Pesa Daraja API integration stub

class DarajaAPI:
    """Stub for M-Pesa Daraja API - implement when credentials available"""
    
    def __init__(self):
        pass
    
    def stk_push(self, phone_number, amount, account_reference):
        """Initiate STK push"""
        raise NotImplementedError("M-Pesa integration not configured")
    
    def check_transaction_status(self, checkout_request_id):
        """Check transaction status"""
        raise NotImplementedError("M-Pesa integration not configured")
