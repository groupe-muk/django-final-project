from . import views
from django.urls import path

urlpatterns = [
    path("", views.home, name="home"),
    path("api/translate/", views.translate_api, name="translate_api"),
    path("transcribe/", views.transcribe_audio, name='transcribe_audio'),
    path("translator/", views.translator, name="translator"),
    path("history/", views.history, name="history"),
    path("history/edit/<int:id>/", views.edit_history, name="edit_history"),
    path("history/delete/<int:id>/", views.delete_history, name="delete_history"),
    path("history/clear/", views.clear_history, name="clear_history"),
]
