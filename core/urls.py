from django.urls import path
from .views import home, translator, history
from . import views

urlpatterns = [
    path("", home, name="home"),
    path("transcribe/", views.transcribe_audio, name='transcribe_audio'),
    path("translator/", translator, name="translator"),
    path("history/", history, name="history"),
]
