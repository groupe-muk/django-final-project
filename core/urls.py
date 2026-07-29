from . import views
from django.urls import path

urlpatterns = [
    path("", views.home, name="home"),
    path("health/", views.health, name="health"),
    path("api/translate/", views.translate_api, name="translate_api"),
    path(
        "api/translate-document/",
        views.translate_document,
        name="translate_document",
    ),
    path(
        "api/download-translation/",
        views.download_translation,
        name="download_translation",
    ),
    path("transcribe/", views.transcribe_audio, name='transcribe_audio'),
    path("translator/", views.translator, name="translator"),
    path("history/", views.history, name="history"),
    path("history/edit/<int:id>/", views.edit_history, name="edit_history"),
    path("history/delete/<int:id>/", views.delete_history, name="delete_history"),
    path(
        "history/download/<int:id>/",
        views.download_history_translation,
        name="download_history_translation",
    ),
    path("history/clear/", views.clear_history, name="clear_history"),
]
