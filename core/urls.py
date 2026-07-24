from django.urls import path
from . import views
urlpatterns = [
    path("history/", views.history, name="history"),
    path("history/delete/<int:id>/", views.delete_history, name="delete_history"),
    path("history/clear/", views.clear_history, name="clear_history"),
    path("history/reload/<int:id>/",views.reload_translation,name="reload_translation",),
]
