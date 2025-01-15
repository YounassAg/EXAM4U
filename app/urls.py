from django.urls import path
from . import views

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
    path('exams/teacher/<int:exam_id>/rattrapage/', views.rattrapage_exam, name='rattrapage_exam'),
    path('exams/student/<int:exam_id>/rules/', views.exam_rules, name='exam_rules'),
    path('exams/student/<int:exam_id>/take/', views.take_exam, name='take_exam'),
    path('exams/update-status/', views.update_attempt_status, name='update_attempt_status'),
    path('exams/get-status/', views.get_exam_status, name='get_exam_status'),
    path('exams/teacher/<int:exam_id>/delete/', views.delete_exam, name='delete_exam'),
    path('exams/teacher/<int:exam_id>/edit/', views.edit_exam, name='edit_exam'),
    path('exams/teacher/<int:exam_id>/attempts/', views.exam_attempts, name='exam_attempts'),
    path('exams/teacher/attempt/<int:attempt_id>/grade/', views.grade_attempt, name='grade_attempt'),
    path('exams/student/completed/', views.exam_completed, name='exam_completed'),
    path('exams/teacher/<int:exam_id>/download-results/', views.download_exam_results, name='download_exam_results'),
    path('exams/teacher/download-result/<int:attempt_id>/', views.download_student_result, name='download_student_result'),
    path('exams/student/log-action/', views.log_student_action, name='log_action'),
    path('exams/teacher/logs/<int:attempt_id>/', views.view_exam_logs, name='exam_logs'),

    # Quiz URLs - Teacher
    path('teacher/quizzes/', views.teacher_quiz_list, name='teacher_quiz_list'),
    path('teacher/quizzes/create/', views.create_quiz, name='create_quiz'),
    path('teacher/quizzes/<int:quiz_id>/edit/', views.edit_quiz, name='edit_quiz'),
    path('teacher/quizzes/<int:quiz_id>/questions/add/', views.add_quiz_question, name='add_quiz_question'),
    path('teacher/quiz-questions/<int:question_id>/edit/', views.edit_quiz_question, name='edit_quiz_question'),
    path('teacher/quiz-questions/<int:question_id>/delete/', views.delete_quiz_question, name='delete_quiz_question'),
    path('teacher/quizzes/<int:quiz_id>/delete/', views.delete_quiz, name='delete_quiz'),

    # Quiz URLs - Student
    path('student/quizzes/', views.student_quiz_list, name='student_quiz_list'),
    path('student/quizzes/<int:quiz_id>/take/', views.take_quiz, name='take_quiz'),
    path('student/quiz-attempts/<int:attempt_id>/submit/', views.submit_quiz, name='submit_quiz'),
    path('student/quiz-attempts/<int:attempt_id>/results/', views.quiz_results, name='quiz_results'),
]
