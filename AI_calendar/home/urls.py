from django.urls import path
from . import views


urlpatterns = [
    path('', views.index, name='home.index'),
    path('add-event/', views.add_event_to_google, name='add_event_to_google'),
    path('delete-event/', views.delete_event_from_google, name='delete_event_from_google'),
]
