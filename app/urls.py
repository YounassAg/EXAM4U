from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('login/', views.user_login, name='login'),
    path('get-groups/<int:specialty_id>/', views.get_groups_by_specialty, name='get_groups_by_specialty'),
    path('register/', views.user_register, name='register'),
    path('logout/', views.user_logout, name='logout'),
    path('teacher/dashboard/', views.teacher_dashboard, name='teacher_dashboard'),
    path('student/dashboard/', views.student_dashboard, name='student_dashboard'),
    path('teacher/courses/', views.teacher_courses, name='teacher_courses'),
    path('student/courses/', views.student_courses, name='student_courses'),
    path('teacher/courses/create/', views.create_course, name='create_course'),
    path('teacher/courses/edit/<int:course_id>/', views.edit_course, name='edit_course'),
    path('teacher/courses/delete/<int:course_id>/', views.delete_course, name='delete_course'),
    path('teacher/exam/create_exam/', views.create_exam, name='create_exam'),
    path('student/exam/exam_list/', views.student_exam_list, name='student_exam_list'),
    path('teacher/exam/exam_list/', views.teacher_exam_list, name='teacher_exam_list'),
    path('teacher/rattrapage/<int:exam_id>/', views.rattrapage_exam, name='rattrapage_exam'),
    path('student/exam/<int:exam_id>/take/', views.take_exam, name='take_exam'),
    path('student/exam/<int:attempt_id>/completed/', views.exam_completed, name='exam_completed'),
    path('teacher/exam/delete_exam/<int:exam_id>/', views.delete_exam, name='delete_exam'),
    path('teacher/exam/edit_exam/<int:exam_id>/', views.edit_exam, name='edit_exam'),
    path('teacher/exam/<int:exam_id>/attempts/', views.exam_attempts, name='exam_attempts'),
    path('teacher/exam/attempt/<int:attempt_id>/correct/', views.grade_attempt, name='grade_attempt'),
    path('teacher/exam/<int:exam_id>/download_results/', views.download_exam_results, name='download_exam_results'),
    path('teacher/exam/download_student_result/<int:attempt_id>/', views.download_student_result, name='download_student_result'),
]
