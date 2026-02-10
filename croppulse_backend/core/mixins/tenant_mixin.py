class TenantMixin:
    pass

class BankContextMixin:
    """Mixin to provide bank context in views"""
    def get_bank(self):
        return getattr(self.request.user, 'bank', None)

