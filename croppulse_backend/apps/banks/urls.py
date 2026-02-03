# apps/banks/urls.py

from django.urls import path
from . import views

app_name = 'banks'

urlpatterns = [
    # --- Bank profile -----------------------------------------------------
    path('profile/',                          views.BankProfileView.as_view(),              name='bank-profile'),

    # --- API Keys ---------------------------------------------------------
    path('api-keys/',                         views.APIKeyListView.as_view(),               name='apikey-list'),
    path('api-keys/create/',                  views.APIKeyCreateView.as_view(),             name='apikey-create'),
    path('api-keys/<int:pk>/revoke/',         views.APIKeyRevokeView.as_view(),             name='apikey-revoke'),
    path('api-keys/<int:pk>/rotate/',         views.APIKeyRotateView.as_view(),             name='apikey-rotate'),

    # --- Webhooks ---------------------------------------------------------
    path('webhooks/',                         views.WebhookListView.as_view(),              name='webhook-list'),
    path('webhooks/create/',                  views.WebhookCreateView.as_view(),            name='webhook-create'),
    path('webhooks/<int:pk>/',                views.WebhookDetailView.as_view(),            name='webhook-detail'),
    path('webhooks/<int:pk>/rotate-secret/',  views.WebhookRotateSecretView.as_view(),      name='webhook-rotate-secret'),

    # --- Webhook Deliveries (read-only) -----------------------------------
    path('webhooks/deliveries/',              views.WebhookDeliveryListView.as_view(),      name='webhookdelivery-list'),

    # --- Usage ------------------------------------------------------------
    path('usage/',                            views.UsageLogListView.as_view(),             name='usage-list'),
    path('usage/summary/',                    views.UsageSummaryView.as_view(),             name='usage-summary'),

    # --- Billing (read-only) ----------------------------------------------
    path('billing/',                          views.BillingRecordListView.as_view(),        name='billing-list'),
    path('billing/<int:pk>/',                 views.BillingRecordDetailView.as_view(),      name='billing-detail'),
]