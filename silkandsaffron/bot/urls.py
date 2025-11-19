from django.urls import path
from . import views

urlpatterns = [
    path('webhook/', views.dialogflow_webhook, name='dialogflow_webhook'),
    path('webhook/health/', views.webhook_health, name='webhook_health'),
]