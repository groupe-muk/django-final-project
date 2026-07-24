from django.urls import path
from .views import home, translator, history

urlpatterns = [
    path("", home, name="home"),
    path("translator/", translator, name="translator"),
    path("history/", history, name="history"),
]
