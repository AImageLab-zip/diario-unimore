from django.contrib import admin
from django.urls import path
from django.views.generic import TemplateView

from activities import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.dashboard, name='dashboard'),
    path('collega-calendar/', views.collega_calendar, name='collega_calendar'),
    path('scollega-calendar/<int:pk>/', views.scollega_calendar, name='scollega_calendar'),
    path('oauth2callback/', views.oauth2callback, name='oauth2callback'),
    path('logout/', views.esci, name='logout'),
    path('accesso-negato/', TemplateView.as_view(
        template_name='activities/accesso_negato.html'), name='accesso_negato'),
]