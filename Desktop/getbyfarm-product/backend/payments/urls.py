from django.urls import path

from .views import InitiatePaymentView, MpesaCallbackView, PaymentStatusView

urlpatterns = [
    path("initiate/", InitiatePaymentView.as_view(), name="payment-initiate"),
    path("status/<uuid:order_id>/", PaymentStatusView.as_view(), name="payment-status"),
    path("mpesa-callback/<str:secret>/", MpesaCallbackView.as_view(), name="mpesa-callback"),
]
