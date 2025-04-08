from django.urls import path
from . import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('', views.index, name='index'),
    path('auth/login/', views.user_login, name='login'),
    path('auth/register/', views.user_register, name='register'),
    path('auth/logout/', views.user_logout, name='logout'),
    path('groups/<int:specialty_id>/', views.get_groups_by_specialty, name='get_groups_by_specialty'),

    path('dashboard/teacher/', views.teacher_dashboard, name='teacher_dashboard'),
    path('dashboard/student/', views.student_dashboard, name='student_dashboard'),

    path('courses/teacher/', views.teacher_courses, name='teacher_courses'),
    path('courses/student/', views.student_courses, name='student_courses'),
    path('courses/teacher/create/', views.create_course, name='create_course'),
    path('courses/teacher/<int:course_id>/edit/', views.edit_course, name='edit_course'),
    path('courses/teacher/<int:course_id>/delete/', views.delete_course, name='delete_course'),

    path('exams/teacher/create/', views.create_exam, name='create_exam'),
    path('exams/student/list/', views.student_exam_list, name='student_exam_list'),
    path('exams/teacher/list/', views.teacher_exam_list, name='teacher_exam_list'),
    # path('exams/teacher/<int:exam_id>/rattrapage/', views.rattrapage_exam, name='rattrapage_exam'),
    path('exams/student/<int:exam_id>/rules/', views.exam_rules, name='exam_rules'),
    path('exams/student/<int:exam_id>/take/', views.take_exam, name='take_exam'),

    path('save-answer/', views.save_answer, name='save_answer'),
    path('get-saved-answers/<int:attempt_id>/', views.get_saved_answers, name='get_saved_answers'),

    path('exams/update-status/', views.update_attempt_status, name='update_attempt_status'),
    path('exams/get-status/', views.get_exam_status, name='get_exam_status'),
    path('exams/teacher/<int:exam_id>/delete/', views.delete_exam, name='delete_exam'),
    path('exams/teacher/<int:exam_id>/edit/', views.edit_exam, name='edit_exam'),
    path('exams/teacher/<int:exam_id>/attempts/', views.exam_attempts, name='exam_attempts'),
    path('exam/<int:exam_id>/attempts/json/', views.get_exam_attempts_json, name='get_exam_attempts_json'),
    path('exams/<int:exam_id>/mark-all-completed/', views.mark_all_attempts_completed, name='mark_all_attempts_completed'),
    path('reset-is-taking-exam/<str:username>/', views.reset_is_taking_exam, name='reset_is_taking_exam'),
    path('exams/teacher/attempt/<int:attempt_id>/grade/', views.grade_attempt, name='grade_attempt'),
    path('exams/student/completed/', views.exam_completed, name='exam_completed'),
    path('exams/teacher/<int:exam_id>/download-results/', views.download_exam_results, name='download_exam_results'),
    path('exams/teacher/download-result/<int:attempt_id>/', views.download_student_result, name='download_student_result'),
    path('exams/student/log-action/', views.log_student_action, name='log_action'),
    path('exams/teacher/logs/<int:attempt_id>/', views.view_exam_logs, name='exam_logs'),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)