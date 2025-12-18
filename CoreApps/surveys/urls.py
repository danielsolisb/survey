from django.urls import path
from .views import WellListView, WellDetailView, SurveyImportView, DownloadTemplateView
from .delete_view import TrajectoryDeleteView

app_name = 'surveys'

urlpatterns = [
    path('wells/', WellListView.as_view(), name='well_list'),
    path('wells/<uuid:pk>/', WellDetailView.as_view(), name='well_detail'),
    path('wells/<uuid:pk>/import/', SurveyImportView.as_view(), name='survey_import'),
    path('template/download/', DownloadTemplateView.as_view(), name='download_template'),
    path('trajectory/<int:pk>/delete/', TrajectoryDeleteView.as_view(), name='trajectory_delete'),
]
