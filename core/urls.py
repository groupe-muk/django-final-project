from django.urls import path
from .views import home
from . import views

urlpatterns = [
    path("", home, name="home"),
    path("transcribe/", views.transcribe_audio, name='transcribe_audio'),
]
