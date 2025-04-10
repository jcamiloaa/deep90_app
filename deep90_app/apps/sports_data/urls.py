from django.urls import path
from . import views

app_name = "sports_data"

urlpatterns = [
    path("", views.DashboardView.as_view(), name="dashboard"),
    path("tasks/", views.TaskListView.as_view(), name="task-list"),
    path("tasks/<int:pk>/", views.TaskDetailView.as_view(), name="task-detail"),
    path("tasks/<int:pk>/execute/", views.ExecuteTaskView.as_view(), name="execute-task"),
    path("tasks/<int:pk>/edit/", views.EditTaskView.as_view(), name="edit-task"),
    path("tasks/<int:pk>/cancel/", views.CancelTaskView.as_view(), name="cancel-task"),
    path("results/<int:pk>/", views.ResultDetailView.as_view(), name="result-detail"),
    path("create-task/", views.CreateTaskWizardView.as_view(), name="create-task-wizard"),
    path("create-task/<int:step>/", views.CreateTaskWizardView.as_view(), name="create-task-wizard"),
]