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
    path("tasks/create/", views.CreateTaskWizardView.as_view(), name="create-task-wizard"),
    path("tasks/create/<int:step>/", views.CreateTaskWizardView.as_view(), name="create-task-wizard"),
    path("results/<int:pk>/", views.ResultDetailView.as_view(), name="result-detail"),
    
    # Rutas para el dashboard de datos en vivo
    path("live/", views.live_dashboard, name="live-dashboard"),
    path("api/toggle-live-task/<str:task_type>/<int:task_id>/", views.toggle_live_task, name="toggle-live-task"),
    path("api/restart-live-task/<str:task_type>/<int:task_id>/", views.restart_live_task, name="restart-live-task"),
    # Nueva ruta para reiniciar tareas con next_run en el pasado
    path("api/reset-stalled-tasks/<str:task_type>/<int:task_id>/", views.reset_stalled_task, name="reset-stalled-task"),
    path("api/reset-all-stalled-tasks/", views.reset_all_stalled_tasks, name="reset-all-stalled-tasks"),
    
    # Nueva ruta para ver detalles de las cuotas de un partido específico
    path("fixture/<int:fixture_id>/odds/", views.fixture_odds_detail, name="fixture-odds-detail"),
    # Nueva ruta para ver solo el widget de un partido específico
    path("fixture/<int:fixture_id>/widget/", views.fixture_widget, name="fixture-widget"),

    # Endpoints para ejecutar manualmente las tareas de live fixtures y live odds
    path("api/run-update-live-fixtures/", views.run_update_live_fixtures, name="run-update-live-fixtures"),
    path("api/run-update-live-odds/", views.run_update_live_odds, name="run-update-live-odds"),
]