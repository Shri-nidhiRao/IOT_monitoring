from django.contrib import admin
from django.urls import path
from iot_api import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('test-http', views.test_http, name='test_http'),
    path('update-http', views.update_data_http, name='update_data_http'),
    path('schedule-http', views.schedule_data_http, name='schedule_data_http'),
    path('update', views.update_data, name='update_data'),
    path('latest', views.latest_data, name='latest_data'),
    path('latest/id/<str:device_id>', views.latest_by_id, name='latest_by_id'),
    path('latest/name/<str:device_name>', views.latest_by_name, name='latest_by_name'),
    path('history', views.history_data, name='history_data'),
    path('history/id/<str:device_id>', views.history_by_id, name='history_by_id'),
    path('history/name/<str:device_name>', views.history_by_name, name='history_by_name'),
    path('schedule', views.schedule_data, name='schedule_data'),
    path('schedule-history', views.schedule_history_data, name='schedule_history_data'),
    path('health', views.health, name='health'),
]
