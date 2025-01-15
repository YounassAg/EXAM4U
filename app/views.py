from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction, IntegrityError
from django.core.exceptions import PermissionDenied
from django.utils.timezone import now
from django.db.models import Avg, Count, F, DurationField, ExpressionWrapper, DecimalField
from django.db.models.functions import Cast
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from .forms import UserRegistrationForm, LoginForm, ExamForm, QuizForm, QuizQuestionForm, QuizChoiceFormSet
from .models import Course, Group, Exam, Question, MCQChoice, UserProfile, Specialty, ExamAttempt, Response, StudentActionLog, Quiz, QuizQuestion, QuizChoice, QuizAttempt, QuizResponse
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.colors import HexColor
from django.db.models import F, Value, CharField
from django.db.models.functions import Concat
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Preformatted
from reportlab.lib.units import inch
import zipfile
import json
from reportlab.pdfgen import canvas
from io import BytesIO
import csv
import re
import random



def role_required(role):
    def decorator(view_func):
        def _wrapped_view(request, *args, **kwargs):
            if request.user.is_authenticated and request.user.userprofile.role == role:
                return view_func(request, *args, **kwargs)
            else:
                raise PermissionDenied
        return _wrapped_view
    return decorator


def index(request):
    return render(request, 'index.html')


def get_groups_by_specialty(request, specialty_id):
    groups = Group.objects.filter(specialty_id=specialty_id).values('id', 'group_code', 'year')
    return JsonResponse(list(groups), safe=False)


def user_register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password1')
            user = authenticate(username=username, password=password)
            login(request, user)
            user_profile = UserProfile.objects.get(user=user)
            if user_profile.role == 'teacher':
                return redirect('teacher_dashboard')
            else:
                return redirect('student_dashboard')
    else:
        form = UserRegistrationForm()
    groups = Group.objects.all()
    specialties = Specialty.objects.all()
    return render(request, 'auth/register.html', {
        'form': form,
        'groups': groups,
        'specialties': specialties
    })


def user_login(request):
    if request.method == 'POST':
        form = LoginForm(request, data=request.POST)
        if form.is_valid():
            username = form.cleaned_data.get('username')
            password = form.cleaned_data.get('password')
            user = authenticate(username=username, password=password)
            if user is not None:
                login(request, user)
                user_profile = UserProfile.objects.get(user=user)
                if user_profile.role == 'teacher':
                    return redirect('teacher_dashboard')
                else:
                    return redirect('student_dashboard')
    else:
        form = LoginForm()
    return render(request, 'auth/login.html', {'form': form})


def user_logout(request):
    logout(request)
    return redirect('index')


@login_required
@role_required('teacher')
def teacher_dashboard(request):
    teacher_profile = request.user.userprofile
    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    
    upcoming_exams = Exam.objects.filter(
        course__teacher=teacher_profile,
        start_date__gt=now
    ).order_by('start_date')[:5]
    
    recent_activities = []
    
    # Add recent exam completions
    recent_completions = ExamAttempt.objects.filter(
        exam__course__teacher=teacher_profile,
        status='completed',
        modified_at__gte=last_30_days
    ).select_related('student', 'exam')[:5]
    
    for completion in recent_completions:
        recent_activities.append({
            'type': 'exam_completed',
            'description': f"{completion.student} - {completion.exam.title}",
            'timestamp': completion.modified_at,
            'grade': completion.grade if completion.grade is not None else 'Pas encore corrigé'
        })

    for exam in upcoming_exams:
        recent_activities.append({
            'type': 'exam_upcoming',
            'description': f"Examen à venir: {exam.title} pour {exam.group}",
            'timestamp': exam.start_date,
            'days_until': (exam.start_date.date() - now.date()).days
        })
    
    recent_activities.sort(key=lambda x: x['timestamp'], reverse=True)
    
    context = {
        'upcoming_exams': upcoming_exams,
        'recent_activities': recent_activities[:5]
    }
    
    return render(request, 'teacher/dashboard.html', context)

@login_required
@role_required('teacher')
def teacher_courses(request):
    teacher = request.user.userprofile
    courses = Course.objects.filter(teacher=teacher)
    return render(request, 'teacher/courses/courses.html', {'courses': courses})



@login_required
@role_required('student')
def student_courses(request):
    student_specialty = request.user.userprofile.specialty
    courses = Course.objects.filter(specialty=student_specialty)
    return render(request, 'student/courses/courses.html', {'courses': courses})


@login_required
@role_required('student')
def student_dashboard(request):
    return render(request, 'student/dashboard.html')


@login_required
@role_required('teacher')
def create_exam(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                title = request.POST.get('title')
                description = request.POST.get('description')
                course_id = request.POST.get('course')
                group_id = request.POST.get('group')
                duration = request.POST.get('duration')
                max_attempts = request.POST.get('max_attempts')
                start_date = request.POST.get('start_date')
                end_date = request.POST.get('end_date')
                course = Course.objects.get(id=course_id)
                group = Group.objects.get(id=group_id)
                exam = Exam.objects.create(
                    title=title,
                    description=description,
                    course=course,
                    group=group,
                    duration=duration,
                    max_attempts=max_attempts,
                    start_date=start_date,
                    end_date=end_date,
                )
                active_questions = []
                question_count = int(request.POST.get('question_count', 0))
                
                for i in range(1, question_count + 1):
                    # Check if this question slot is actually being used
                    if request.POST.get(f'question_wording_{i}'):
                        question_type = request.POST.get(f'question_type_{i}')
                        question_wording = request.POST.get(f'question_wording_{i}')
                        question_points = request.POST.get(f'question_points_{i}')
                        
                        question = Question.objects.create(
                            exam=exam,
                            question_type=question_type,
                            wording=question_wording,
                            points=question_points,
                            allow_multiple_answers=(question_type == 'MCQ')
                        )
                        active_questions.append(question.id)
                    if question_type == 'MCQ':
                        active_choices = []
                        choice_count = int(request.POST.get(f'mcq_choice_count_{i}', 0))
                        for j in range(1, choice_count + 1):
                            if request.POST.get(f'mcq_choice_text_{i}_{j}'):
                                choice_label = request.POST.get(f'mcq_choice_text_{i}_{j}')
                                is_correct = request.POST.get(f'mcq_choice_correct_{i}_{j}') == 'on'
                                choice = MCQChoice.objects.create(
                                    question=question,
                                    choice_label=choice_label,
                                    is_correct=is_correct
                                )
                                active_choices.append(choice.id)
                messages.success(request, 'Exam created successfully!')
                return redirect('teacher_exam_list')
        except IntegrityError:
            messages.error(request, 'There was an error creating the exam. Please try again.')
            return redirect('teacher_exam_list')
    else:
        courses = Course.objects.filter(teacher__user=request.user)
        groups = Group.objects.all()
        return render(request, 'teacher/exam/create_exam.html', {
            'courses': courses,
            'groups': groups
        })
    exam = get_object_or_404(Exam, id=exam_id)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                title = request.POST.get('title')
                description = request.POST.get('description')
                course_id = request.POST.get('course')
                group_id = request.POST.get('group')
                duration = request.POST.get('duration')
                max_attempts = request.POST.get('max_attempts')
                start_date = request.POST.get('start_date')
                end_date = request.POST.get('end_date')
                course = Course.objects.get(id=course_id)
                group = Group.objects.get(id=group_id)
                exam.title = title
                exam.description = description
                exam.course = course
                exam.group = group
                exam.duration = duration
                exam.max_attempts = max_attempts
                exam.start_date = start_date
                exam.end_date = end_date
                exam.save()
                question_count = int(request.POST.get('question_count', 0))
                for i in range(1, question_count + 1):
                    question_id = request.POST.get(f'question_id_{i}')
                    question_type = request.POST.get(f'question_type_{i}')
                    question_wording = request.POST.get(f'question_wording_{i}')
                    question_points = request.POST.get(f'question_points_{i}')
                    if question_id:
                        question = Question.objects.get(id=question_id)
                        question.question_type = question_type
                        question.wording = question_wording
                        question.points = question_points
                        question.save()
                    else:
                        question = Question.objects.create(
                            exam=exam,
                            question_type=question_type,
                            wording=question_wording,
                            points=question_points,
                            allow_multiple_answers=(question_type == 'MCQ')
                        )
                    if question_type == 'MCQ':
                        choice_count = int(request.POST.get(f'mcq_choice_count_{i}', 0))
                        MCQChoice.objects.filter(question=question).delete()
                        for j in range(1, choice_count + 1):
                            choice_label = request.POST.get(f'mcq_choice_text_{i}_{j}')
                            is_correct = request.POST.get(f'mcq_choice_correct_{i}_{j}') == 'on'
                            MCQChoice.objects.create(
                                question=question,
                                choice_label=choice_label,
                                is_correct=is_correct
                            )
                deleted_question_ids = request.POST.getlist('deleted_question_ids')
                for question_id in deleted_question_ids:
                    question = Question.objects.get(id=question_id)
                    question.delete()
                messages.success(request, 'Exam updated successfully!')
                return redirect('teacher_exam_list')
        except Exception as e:
            messages.error(request, f'There was an error: {str(e)}')
            return redirect('teacher_exam_list')
    else:
        courses = Course.objects.filter(teacher__user=request.user)
        groups = Group.objects.all()

        return render(request, 'teacher/exam/edit_exam.html', {
            'exam': exam,
            'courses': courses,
            'groups': groups
        })


@login_required
@role_required('teacher')
def edit_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                exam.title = request.POST.get('title')
                exam.description = request.POST.get('description')
                exam.course = Course.objects.get(id=request.POST.get('course'))
                exam.group = Group.objects.get(id=request.POST.get('group'))
                exam.duration = request.POST.get('duration')
                exam.max_attempts = request.POST.get('max_attempts')
                exam.start_date = request.POST.get('start_date')
                exam.end_date = request.POST.get('end_date')
                exam.save()

                # Track existing and processed questions
                existing_questions = set(exam.question_set.values_list('id', flat=True))
                processed_questions = set()

                # Get the updated question count
                question_count = int(request.POST.get('question_count', 0))

                for i in range(1, question_count + 1):
                    if all(request.POST.get(f'question_{field}_{i}') is not None 
                        for field in ['type', 'wording', 'points']):
                        question_id = request.POST.get(f'question_id_{i}')
                        question_type = request.POST.get(f'question_type_{i}')
                        question_wording = request.POST.get(f'question_wording_{i}')
                        question_points = request.POST.get(f'question_points_{i}')

                    if question_id:
                        question = Question.objects.get(id=question_id)
                        processed_questions.add(int(question_id))
                        question.question_type = question_type
                        question.wording = question_wording
                        question.points = question_points
                        question.allow_multiple_answers = (question_type == 'MCQ')
                        question.save()
                    else:
                        question = Question(exam=exam)

                    # Update question fields
                    question.question_type = question_type
                    question.wording = question_wording
                    question.points = question_points
                    question.allow_multiple_answers = (question_type == 'MCQ')
                    question.save()

                    if question_id:
                        processed_questions.add(int(question_id))

                    if question_type == 'MCQ':
                        MCQChoice.objects.filter(question=question).delete()
                        choice_count = int(request.POST.get(f'mcq_choice_count_{i}', 0))
                        for j in range(1, choice_count + 1):
                            choice_text = request.POST.get(f'mcq_choice_text_{i}_{j}')
                            is_correct = request.POST.get(f'mcq_choice_correct_{i}_{j}') == 'on'
                            if choice_text:
                                MCQChoice.objects.create(
                                    question=question,
                                    choice_label=choice_text,
                                    is_correct=is_correct
                                )
                                
                questions_to_delete = existing_questions - processed_questions
                Question.objects.filter(id__in=questions_to_delete).delete()
                messages.success(request, 'Exam updated successfully!')
                return redirect('teacher_exam_list')
        except Exception as e:
            messages.error(request, f'Error updating exam: {str(e)}')
            return redirect('edit_exam', exam_id=exam_id)
    else:
        courses = Course.objects.filter(teacher__user=request.user)
        groups = Group.objects.all()
        questions = exam.question_set.all().prefetch_related('mcqchoice_set')
        context = {
            'exam': exam,
            'courses': courses,
            'groups': groups,
            'questions': questions,
        }
        return render(request, 'teacher/exam/edit_exam.html', context)
    

@login_required
@role_required('student')
def student_exam_list(request):
    student_group = request.user.userprofile.group
    exams = Exam.objects.filter(group=student_group).order_by('-start_date')
    completed_exams = ExamAttempt.objects.filter(
        student=request.user.userprofile,
        status='completed'
    ).values_list('exam_id', flat=True)
    context = {
        'exams': exams,
        'completed_exams': completed_exams,
    }
    return render(request, 'student/exam/exam_list.html', context)


@login_required
@role_required('teacher')
def teacher_exam_list(request):
    teacher_profile = request.user.userprofile
    exams = Exam.objects.filter(course__teacher=teacher_profile).order_by('-start_date')
    return render(request, 'teacher/exam/exam_list.html', {'exams': exams})


@login_required
@csrf_exempt
def update_attempt_status(request):
    if request.method == 'POST':
        try:
            attempt_id = request.POST.get('attempt_id')
            status = request.POST.get('status')  # e.g., "abandoned"
            attempt = ExamAttempt.objects.get(id=attempt_id, student=request.user.userprofile)
            attempt.status = status
            attempt.save()
            return JsonResponse({'success': True, 'message': 'Attempt status updated successfully.'})
        except ExamAttempt.DoesNotExist:
            return JsonResponse({'success': False, 'message': 'Attempt not found.'}, status=404)
    return JsonResponse({'success': False, 'message': 'Invalid request method.'}, status=400)


@login_required
@role_required('student')
def take_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    current_time = now()

    # Check if the current time is outside the allowed exam window
    if current_time < exam.start_date:
        messages.error(request, "Cet examen n'a pas encore commencé.")
        return redirect('student_exam_list')
    elif current_time > exam.end_date:
        messages.error(request, "Cet examen est déjà terminé.")
        return redirect('student_exam_list')

    student = request.user.userprofile
    attempt = ExamAttempt.objects.filter(exam=exam, student=student, status__in=['in_progress', 'abandoned']).first()

    if not attempt:
        completed_or_abandoned_attempts = ExamAttempt.objects.filter(
            exam=exam, student=student, status__in=['completed']
        ).count()
        if completed_or_abandoned_attempts >= exam.max_attempts:
            messages.error(request, f"Vous avez déjà atteint le nombre maximum de tentatives {exam.max_attempts} pour l'examen '{exam.title}'.")
            return redirect('student_exam_list')
        attempt = ExamAttempt.objects.create(exam=exam, student=student, status='in_progress', start_date=timezone.now())

    questions = Question.objects.filter(exam=exam).prefetch_related('mcqchoice_set')

    if request.method == 'POST':
        form = ExamForm(request.POST, questions=questions)
        if form.is_valid():
            for question in questions:
                if question.question_type == 'MCQ':
                    response_data = form.cleaned_data[f'question_{question.id}']
                    if question.allow_multiple_answers:
                        selected_choices = MCQChoice.objects.filter(id__in=response_data)
                        response_text = ' ~±ſ~ƟƢ~ '.join([choice.choice_label for choice in selected_choices])
                    else:
                        selected_choice = MCQChoice.objects.get(id=response_data)
                        response_text = selected_choice.choice_label
                else:
                    response_text = form.cleaned_data[f'question_{question.id}']
                    if not response_text or not response_text.strip():
                        response_text = "Not Answered"
                Response.objects.create(
                    attempt=attempt,
                    question=question,
                    response_text=response_text
                )
            attempt.status = 'completed'
            attempt.end_date = timezone.now()
            attempt.save()
            return redirect('exam_completed')
    else:
        initial_responses = {
            f'question_{response.question.id}': response.response_text
            for response in attempt.response_set.all()
        }
        form = ExamForm(questions=questions, initial=initial_responses)

    return render(request, 'student/exam/take_exam.html', {
        'exam': exam,
        'form': form,
        'questions': questions,
        'attempt': attempt,
    })

@csrf_exempt
def log_student_action(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        attempt_id = data.get('attempt_id')
        action = data.get('action')
        details = data.get('details', '')

        attempt = ExamAttempt.objects.filter(id=attempt_id).first()
        if attempt:
            StudentActionLog.objects.create(
                attempt=attempt,
                action=action,
                details=details
            )
            return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error', 'message': 'Invalid request'}, status=400)

@login_required
@role_required('teacher')
def view_exam_logs(request, attempt_id):
    attempt = get_object_or_404(ExamAttempt, id=attempt_id)
    logs = StudentActionLog.objects.filter(attempt=attempt).order_by('timestamp')

    return render(request, 'teacher/exam/exam_logs.html', {
        'attempt': attempt,
        'logs': logs,
    })


@login_required
@role_required('teacher')
def rattrapage_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    students = UserProfile.objects.filter(group=exam.group, role='student')
    if request.method == 'POST':
        selected_students = request.POST.getlist('students')
        for student_id in selected_students:
            student = UserProfile.objects.get(id=student_id)
            ExamAttempt.objects.create(
                exam=exam,
                student=student,
                type='rattrapage'
            )
            messages.success(request, f"Exam attempt created for {student.first_name} {student.last_name}.")
        return redirect('teacher_exam_list')
    return render(request, 'teacher/exam/rattrapage_exam.html', {
        'exam': exam,
        'students': students
    })


@login_required
@role_required('teacher')
def delete_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    if request.method == 'POST':
        exam.delete()
        messages.success(request, "Exam deleted successfully.")
        return redirect('teacher_exam_list')  # Redirect to the exam list page

    return render(request, 'teacher/exam/delete_exam.html', {'exam': exam})

@login_required
@role_required('teacher')
def get_exam_status(request, exam_id):
    exam = Exam.objects.get(id=exam_id)
    attempts = ExamAttempt.objects.filter(exam=exam).values(
        'id',
        'start_date',
        'status',
        'grade',
        full_name=Concat(
            F('student__user__first_name'),
            Value(' '),
            F('student__user__last_name'),
            output_field=CharField()
        )
    )
    return JsonResponse({'attempts': list(attempts)})

@login_required
@role_required('teacher')
def exam_attempts(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    attempts = ExamAttempt.objects.filter(exam=exam)
    for attempt in attempts:
        if attempt.end_date and attempt.start_date:
            attempt.time_taken = (attempt.end_date - attempt.start_date).total_seconds() / 60
        else:
            attempt.time_taken = None
    context = {
        'exam': exam,
        'attempts': attempts,
    }
    return render(request, 'teacher/exam/exam_attempts.html', context)

@login_required
@role_required('teacher')
def grade_attempt(request, attempt_id):
    attempt = get_object_or_404(ExamAttempt.objects.select_related(
        'exam', 'student', 'student__user', 'exam__course'
    ), id=attempt_id)
    
    if request.user.userprofile.role != 'teacher' or request.user.userprofile != attempt.exam.course.teacher:
        messages.error(request, "Vous n'avez pas la permission de corriger cet examen.")
        return redirect('dashboard')
    
    responses = Response.objects.filter(
        attempt=attempt
    ).select_related(
        'question'
    ).prefetch_related(
        'question__mcqchoice_set'
    )
    
    if request.method == 'POST':
        total_points = 0
        total_possible_points = 0
        for response in responses:
            response_grade = float(request.POST.get(f'grade_{response.id}', 0))
            response.response_grade = response_grade
            response.save()
            total_points += response_grade
            total_possible_points += response.question.points
        final_grade = total_points if total_possible_points > 0 else 0
        attempt.grade = final_grade
        attempt.status = 'completed'
        attempt.save()
        messages.success(request, 'La correction a été enregistrée avec succès!')
        return redirect('exam_attempts', exam_id=attempt.exam.id)
    
    responses_data = []
    for response in responses:
        responses_data.append({
            'response': response,
            'suggested_grade': response.response_grade if response.response_grade is not None else None
        })
    
    context = {
        'attempt': attempt,
        'responses_data': responses_data,
    }
    return render(request, 'teacher/exam/correct_exam.html', context)


@login_required
@role_required('student')
def exam_completed(request):
    return render(request, 'student/exam/exam_completed.html')


@login_required
@role_required('teacher')
def create_course(request):
    if request.method == 'POST':
        try:
            with transaction.atomic():
                title = request.POST.get('title')
                description = request.POST.get('description')
                specialty_id = request.POST.get('specialty')
                specialty = Specialty.objects.get(id=specialty_id)
                teacher = request.user.userprofile
                course = Course.objects.create(
                    title=title,
                    description=description,
                    specialty=specialty,
                    teacher=teacher
                )
                messages.success(request, 'Cours créé avec succès!')
                return redirect('teacher_courses')
        except IntegrityError:
            messages.error(request, 'Une erreur est survenue lors de la création du cours. Veuillez réessayer.')
            return redirect('teacher_courses')
    else:
        specialties = Specialty.objects.all()
        return render(request, 'teacher/courses/create_course.html', {
            'specialties': specialties
        })


@login_required
@role_required('teacher')
def edit_course(request, course_id):
    course = get_object_or_404(Course, id=course_id, teacher=request.user.userprofile)
    if request.method == 'POST':
        try:
            with transaction.atomic():
                title = request.POST.get('title')
                description = request.POST.get('description')
                duration = request.POST.get('duration')
                specialty_id = request.POST.get('specialty')
                specialty = Specialty.objects.get(id=specialty_id)
                course.title = title
                course.description = description
                course.duration = duration
                course.specialty = specialty
                course.save()
                messages.success(request, 'Cours modifié avec succès!')
                return redirect('teacher_courses')
        except IntegrityError:
            messages.error(request, 'Une erreur est survenue lors de la modification du cours. Veuillez réessayer.')
            return redirect('teacher_courses')
    else:
        specialties = Specialty.objects.all()
        return render(request, 'teacher/courses/edit_course.html', {
            'course': course,
            'specialties': specialties
        })


@login_required
@role_required('teacher')
def delete_course(request, course_id):
    course = get_object_or_404(Course, id=course_id, teacher=request.user.userprofile)   
    if request.method == 'POST':
        try:
            course.delete()
            messages.success(request, 'Cours supprimé avec succès!')
        except Exception as e:
            messages.error(request, 'Une erreur est survenue lors de la suppression du cours.')
        return redirect('teacher_courses')     
    return render(request, 'teacher/courses/delete_course.html', {'course': course})


@login_required
@role_required('teacher')
def download_exam_results(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    group = exam.group
    file_format = request.GET.get('format', 'full')
    students_in_group = UserProfile.objects.filter(group=group, role='student')
    questions = exam.question_set.all()
    if file_format == 'zip':
        zip_buffer = BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
            for student in students_in_group:
                best_attempt = ExamAttempt.objects.filter(exam=exam, student=student).order_by('-grade').first()
                if not best_attempt:
                    continue
                pdf_buffer = BytesIO()
                doc = SimpleDocTemplate(
                    pdf_buffer,
                    pagesize=letter,
                    rightMargin=72,
                    leftMargin=72,
                    topMargin=72,
                    bottomMargin=72
                )
                styles = getSampleStyleSheet()
                elements = []

                logo = Image("templates/components/images/ofppt-header.png")
                logo.drawWidth = 6 * inch
                logo.drawHeight = logo.drawWidth * (325 / 1419)
                elements.append(logo)
                elements.append(Spacer(1, 20))
                code_style = ParagraphStyle(
                    'CodeStyle',
                    parent=styles['Code'],
                    fontName='Courier',
                    fontSize=10,
                    leftIndent=40,
                    rightIndent=20,
                    spaceAfter=12,
                    backColor=HexColor('#f8f9fa'),
                    borderColor=HexColor('#e9ecef'),
                    borderWidth=1,
                    borderPadding=8,
                    borderRadius=5
                )
                grade_style = ParagraphStyle(
                    'GradeStyle',
                    parent=styles['Normal'],
                    fontSize=11,
                    textColor=HexColor('#1e88e5'),
                    leftIndent=20,
                    spaceAfter=20
                )
                correct_answer_style = ParagraphStyle(
                    'CorrectAnswerStyle',
                    parent=styles['Normal'],
                    fontSize=11,
                    leftIndent=20,
                    textColor=HexColor('#2e7d32'),
                    spaceAfter=6
                )
                incorrect_answer_style = ParagraphStyle(
                    'IncorrectAnswerStyle',
                    parent=styles['Normal'],
                    fontSize=11,
                    leftIndent=20,
                    textColor=HexColor('#c62828'), 
                    spaceAfter=6
                )
                student_info = [
                    ['Nom et prénom:', f"{student.first_name} {student.last_name}"],
                    ['CIN:', student.user.username],
                    ['Contrôle:', exam.title],
                    ['Date:', ""],
                    ['Note finale:', f"{best_attempt.grade}/20" if best_attempt.grade is not None else "Non noté"]
                ]
                info_table = Table(student_info, colWidths=[2 * inch, 4 * inch])
                info_table.setStyle(TableStyle([
                    ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 0), (-1, -1), 11),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
                    ('TOPPADDING', (0, 0), (-1, -1), 12),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f8f9fa')),
                    ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#2c3e50')),
                    ('GRID', (0, 0), (-1, -1), 1, HexColor('#e9ecef')),
                    ('BORDERCOLOR', (0, 0), (-1, -1), HexColor('#e9ecef')),
                    ('ALIGN', (1, 0), (1, -1), 'LEFT'),
                ]))
                elements.append(info_table)
                elements.append(Spacer(1, 30))

                responses = Response.objects.filter(attempt=best_attempt)
                for i, response in enumerate(responses, 1):
                    question_text = f"Question {i}: {response.question.wording}"
                    elements.append(Paragraph(question_text, styles['Heading4']))

                    if response.question.question_type == 'MCQ':
                        correct_choices = MCQChoice.objects.filter(
                            question=response.question, is_correct=True
                        ).values_list('choice_label', flat=True)
                        cleaned_response = response.response_text.replace('~±■~■■~', ' ~±ſ~ƟƢ~ ')
                        student_answers = [ans.strip() for ans in cleaned_response.split(' ~±ſ~ƟƢ~ ')]

                        elements.append(Paragraph("Réponses choisies:", styles['Normal']))
                        for answer in student_answers:
                            if not answer:
                                continue
                            
                            is_correct = any(correct_choice.strip() == answer.strip() 
                                        for correct_choice in correct_choices)
                            
                            style = correct_answer_style if is_correct else incorrect_answer_style
                            
                            elements.append(Paragraph(answer, style))

                    elif response.question.question_type == 'open':
                        elements.append(Paragraph("Réponse:", styles['Normal']))
                        cleaned_text = clean_text(response.response_text)
                        elements.append(Preformatted(cleaned_text, code_style))

                    else:
                        elements.append(Paragraph(f"Réponse: {clean_text(response.response_text)}", styles['Normal']))

                    grade_text = f"★ Note: {response.response_grade}/{response.question.points}" if response.response_grade is not None else "☐ Non noté"
                    elements.append(Paragraph(grade_text, grade_style))
                    elements.append(Spacer(1, 15))

                doc.build(elements, canvasmaker=NumberedCanvas)
                pdf_buffer.seek(0)
                pdf_filename = f"{student.last_name}_{student.first_name}_{exam.title}.pdf"
                zip_file.writestr(pdf_filename, pdf_buffer.getvalue())
                pdf_buffer.close()

        zip_buffer.seek(0)
        response = HttpResponse(zip_buffer, content_type='application/zip')
        response['Content-Disposition'] = f'attachment; filename="{exam.title}_results.zip"'
        return response

    elif file_format == 'full':
        response = HttpResponse(content_type='text/csv')
        response.charset = 'utf-8'
        response.write('\ufeff')
        response['Content-Disposition'] = f'attachment; filename="{exam.title}_full_results.csv"'
        writer = csv.writer(response, quoting=csv.QUOTE_MINIMAL)
        header_row = ['CIN', 'Prenom', 'Nom'] + \
                     [f'{question.wording} ({question.points} points)' for question in questions] + ['Total général'] + ['EMARGEMENT']
        writer.writerow(header_row)
        for student in students_in_group:
            best_attempt = ExamAttempt.objects.filter(exam=exam, student=student).order_by('-grade').first()
            if best_attempt:
                responses = Response.objects.filter(attempt=best_attempt).order_by('question__id')
                row = [student.user.username, student.first_name, student.last_name]
                total_score = 0
                for question in questions:
                    response_obj = responses.filter(question=question).first()
                    question_score = response_obj.response_grade if response_obj else 0
                    row.append(question_score)
                    total_score += question_score
                row.append(total_score)
                writer.writerow(row)
        return response
    
    elif file_format == 'generic':
        response = HttpResponse(content_type='text/csv')
        response.charset = 'utf-8'
        response.write('\ufeff')
        response['Content-Disposition'] = f'attachment; filename="{exam.title}_generic_results.csv"'
        writer = csv.writer(response, quoting=csv.QUOTE_MINIMAL)
        header_row = ['CIN', 'Prenom', 'Nom'] + \
                     [f'Question {i+1}' for i in range(len(questions))] + ['Total général'] + ['EMARGEMENT']
        writer.writerow(header_row)
        for student in students_in_group:
            best_attempt = ExamAttempt.objects.filter(exam=exam, student=student).order_by('-grade').first()
            if best_attempt:
                responses = Response.objects.filter(attempt=best_attempt).order_by('question__id')
                row = [student.user.username, student.first_name, student.last_name]
                total_score = 0
                for question in questions:
                    response_obj = responses.filter(question=question).first()
                    question_score = response_obj.response_grade if response_obj else 0
                    row.append(question_score)
                    total_score += question_score
                row.append(total_score)
                writer.writerow(row)
        return response

    return HttpResponse(
        status=400, 
        content=f"Invalid format '{file_format}'. Supported formats are 'full', 'generic', and 'zip'."
    )


class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        canvas.Canvas.__init__(self, *args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_page_number(num_pages)
            canvas.Canvas.showPage(self)
        canvas.Canvas.save(self)

    def draw_page_number(self, page_count):
        self.setFont("Helvetica", 9)
        self.drawRightString(
            letter[0] - 72,
            72/2,
            f"Page {self._pageNumber} sur {page_count}"
        )
        self.setStrokeColor(HexColor('#CCCCCC'))
        self.line(72, 72/2 + 15, letter[0] - 72, 72/2 + 15)


def clean_text(text):
    text = text.replace('\r\n', '\n').replace('\r', '\n')
    text = ''.join(char for char in text if ord(char) >= 32 or char == '\n')
    text = re.sub(r'[\u200B-\u200D\uFEFF]', '', text)
    text = re.sub(r'\n\s*\n\s*\n+', '\n\n', text)
    lines = text.split('\n')
    lines = [line.rstrip() for line in lines]
    text = '\n'.join(lines).strip()
    return text


def download_student_result(request, attempt_id):
    attempt = get_object_or_404(ExamAttempt, pk=attempt_id)
    responses = Response.objects.filter(attempt=attempt)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=72,
        leftMargin=72,
        topMargin=72,
        bottomMargin=72
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=16,
        textColor=HexColor('#1a237e'),
        spaceAfter=20,
        alignment=1
    )
    question_style = ParagraphStyle(
        'QuestionStyle',
        parent=styles['Normal'],
        fontSize=12,
        fontName='Helvetica-Bold',
        textColor=HexColor('#2c3e50'),
        spaceAfter=6,
        borderPadding=(10, 0, 10, 0),
        backColor=HexColor('#f8f9fa')
    )
    answer_style = ParagraphStyle(
        'AnswerStyle',
        parent=styles['Normal'],
        fontSize=11,
        leftIndent=20,
        spaceAfter=12
    )
    correct_answer_style = ParagraphStyle(
        'CorrectAnswerStyle',
        parent=styles['Normal'],
        fontSize=11,
        leftIndent=20,
        textColor=HexColor('#2e7d32'),
        spaceAfter=6
    )
    incorrect_answer_style = ParagraphStyle(
        'IncorrectAnswerStyle',
        parent=styles['Normal'],
        fontSize=11,
        leftIndent=20,
        textColor=HexColor('#c62828'),
        spaceAfter=6
    )
    code_style = ParagraphStyle(
        'CodeStyle',
        parent=styles['Code'],
        fontName='Courier',
        fontSize=10,
        leftIndent=40,
        rightIndent=20,
        spaceAfter=12,
        backColor=HexColor('#f8f9fa'),
        borderColor=HexColor('#e9ecef'),
        borderWidth=1,
        borderPadding=8,
        borderRadius=5
    )
    grade_style = ParagraphStyle(
        'GradeStyle',
        parent=styles['Normal'],
        fontSize=11,
        textColor=HexColor('#1e88e5'),
        leftIndent=20,
        spaceAfter=20
    )
    elements = []
    logo = Image("templates/components/images/ofppt-header.png")
    logo.drawWidth = 6 * inch
    logo.drawHeight = logo.drawWidth * (325/1419)
    elements.append(logo)
    elements.append(Spacer(1, 20))
    student_info = [
        ['Nom et prénom:', f"{attempt.student.first_name} {attempt.student.last_name}"],
        ['CIN:', attempt.student.user.username],
        ['Contrôle:', attempt.exam.title],
        ['Date:', ''],
        ['Note finale:', f"{attempt.grade}/20" if attempt.grade is not None else "Non noté"]
    ]
    info_table = Table(student_info, colWidths=[2*inch, 4*inch])
    info_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 12),
        ('TOPPADDING', (0, 0), (-1, -1), 12),
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('BACKGROUND', (0, 0), (-1, -1), HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (0, -1), HexColor('#2c3e50')),
        ('GRID', (0, 0), (-1, -1), 1, HexColor('#e9ecef')),
        ('BORDERCOLOR', (0, 0), (-1, -1), HexColor('#e9ecef')),
        ('ALIGN', (1, 0), (1, -1), 'LEFT'),
    ]))
    elements.append(info_table)
    elements.append(Spacer(1, 30))

    for i, response in enumerate(responses, 1):
        question_text = f"Question {i}: {response.question.wording}"
        elements.append(Paragraph(question_text, question_style))
        
        if response.question.question_type == 'MCQ':
            correct_choices = MCQChoice.objects.filter(
                question=response.question,
                is_correct=True
            ).values_list('choice_label', flat=True)
            
            elements.append(Paragraph("Réponses choisies:", answer_style))
            
            if response.response_text:
                cleaned_response = response.response_text.replace('~±■~■■~', ' ~±ſ~ƟƢ~ ')
                student_answers = [ans.strip() for ans in cleaned_response.split(' ~±ſ~ƟƢ~ ')]
                
                for answer in student_answers:
                    if not answer:
                        continue
                    is_correct = any(correct_choice.strip() == answer.strip() 
                                   for correct_choice in correct_choices)
                    style = correct_answer_style if is_correct else incorrect_answer_style
                    elements.append(Paragraph(answer, style))
            
        elif response.question.question_type == 'open':
            elements.append(Paragraph("Réponse:", answer_style))
            cleaned_text = clean_text(response.response_text)
            elements.append(Preformatted(cleaned_text, code_style))
        else:  # short_answer
            elements.append(Paragraph(f"Réponse: {clean_text(response.response_text)}", answer_style))
            
        grade_text = f"★ Note: {response.response_grade}/{response.question.points}" if response.response_grade is not None else "☐ Non noté"
        elements.append(Paragraph(grade_text, grade_style))
        elements.append(Spacer(1, 15))

    doc.build(elements, canvasmaker=NumberedCanvas)
    buffer.seek(0)
    response = HttpResponse(buffer, content_type='application/pdf')
    filename = f"resultat_{attempt.student.last_name}_{attempt.exam.title}.pdf"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def custom_403(request, exception):
    return render(request, 'errors/403.html', status=403)


def custom_404(request, exception):
    return render(request, 'errors/404.html', status=404)

@login_required
@role_required('student')
def exam_rules(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    return render(request, 'student/exam/exam_rules.html', {'exam': exam})

@login_required
@role_required('teacher')
def teacher_quiz_list(request):
    quizzes = Quiz.objects.filter(teacher=request.user.userprofile).order_by('-created_at')
    for quiz in quizzes:
        quiz.total_attempts = quiz.attempts.count()
        quiz.avg_score = quiz.attempts.filter(status='completed').aggregate(Avg('score'))['score__avg']
    return render(request, 'teacher/quiz/quiz_list.html', {'quizzes': quizzes})

@login_required
@role_required('teacher')
def create_quiz(request):
    if request.method == 'POST':
        form = QuizForm(request.POST)
        if form.is_valid():
            quiz = form.save(commit=False)
            quiz.teacher = request.user.userprofile
            quiz.save()
            messages.success(request, 'Quiz créé avec succès.')
            return redirect('edit_quiz', quiz_id=quiz.id)
    else:
        form = QuizForm(initial={'course': request.GET.get('course')})
    return render(request, 'teacher/quiz/quiz_form.html', {'form': form})

@login_required
@role_required('teacher')
def edit_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user.userprofile)
    if request.method == 'POST':
        form = QuizForm(request.POST, instance=quiz)
        if form.is_valid():
            form.save()
            messages.success(request, 'Quiz modifié avec succès.')
            return redirect('teacher_quiz_list')
    else:
        form = QuizForm(instance=quiz)
    
    questions = quiz.questions.all().order_by('order')
    attempts = quiz.attempts.select_related('student').order_by('-start_time')
    
    return render(request, 'teacher/quiz/quiz_form.html', {
        'form': form,
        'quiz': quiz,
        'questions': questions,
        'attempts': attempts
    })

@login_required
@role_required('teacher')
def add_quiz_question(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user.userprofile)
    
    if request.method == 'POST':
        question_form = QuizQuestionForm(request.POST)
        choice_formset = QuizChoiceFormSet(request.POST)
        
        if question_form.is_valid() and choice_formset.is_valid():
            question = question_form.save(commit=False)
            question.quiz = quiz
            question.order = quiz.questions.count() + 1
            question.save()
            
            # Save choices
            choice_formset.instance = question
            choices = choice_formset.save(commit=False)
            for i, choice in enumerate(choices):
                choice.question = question
                choice.order = i + 1
                choice.save()
            
            messages.success(request, 'Question ajoutée avec succès!')
            return redirect('edit_quiz', quiz_id=quiz.id)
        else:
            messages.error(request, 'Veuillez corriger les erreurs ci-dessous.')
    else:
        question_form = QuizQuestionForm()
        choice_formset = QuizChoiceFormSet()
    
    return render(request, 'teacher/quiz/quiz_question_form.html', {
        'quiz': quiz,
        'question_form': question_form,
        'choice_formset': choice_formset,
    })

@login_required
@role_required('teacher')
def edit_quiz_question(request, question_id):
    question = get_object_or_404(QuizQuestion, id=question_id, quiz__teacher=request.user.userprofile)
    
    if request.method == 'POST':
        question_form = QuizQuestionForm(request.POST, instance=question)
        choice_formset = QuizChoiceFormSet(request.POST, instance=question)
        
        if question_form.is_valid() and choice_formset.is_valid():
            question_form.save()
            choices = choice_formset.save(commit=False)
            
            # Update choice order
            for i, choice in enumerate(choices):
                choice.order = i + 1
                choice.save()
            
            # Handle deleted choices
            for obj in choice_formset.deleted_objects:
                obj.delete()
            
            messages.success(request, 'Question mise à jour avec succès!')
            return redirect('edit_quiz', quiz_id=question.quiz.id)
    else:
        question_form = QuizQuestionForm(instance=question)
        choice_formset = QuizChoiceFormSet(instance=question)
    
    return render(request, 'teacher/quiz_question_form.html', {
        'quiz': question.quiz,
        'question_form': question_form,
        'choice_formset': choice_formset,
        'question': question,
        'title': 'Modifier la Question'
    })

@login_required
@role_required('teacher')
def delete_quiz_question(request, question_id):
    question = get_object_or_404(QuizQuestion, id=question_id, quiz__teacher=request.user.userprofile)
    quiz_id = question.quiz.id
    
    # Update order of remaining questions
    questions_to_update = question.quiz.questions.filter(order__gt=question.order)
    for q in questions_to_update:
        q.order -= 1
        q.save()
    
    question.delete()
    messages.success(request, 'Question supprimée avec succès!')
    return redirect('edit_quiz', quiz_id=quiz_id)

@login_required
@role_required('teacher')
def delete_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user.userprofile)
    quiz.delete()
    messages.success(request, 'Quiz supprimé avec succès!')
    return redirect('teacher_quiz_list')

@login_required
@role_required('student')
def student_quiz_list(request):
    student_courses = request.user.userprofile.group.specialty.course_set.all()
    quizzes = Quiz.objects.filter(
        is_published=True,
        course__in=student_courses
    ).order_by('-created_at')
    
    for quiz in quizzes:
        quiz.student_attempts = list(quiz.attempts.filter(student=request.user.userprofile).order_by('-start_time'))
        quiz.best_score = quiz.get_student_best_score(request.user.userprofile)
        quiz.is_available = quiz.is_available_for_student(request.user.userprofile)
    
    return render(request, 'student/quiz/quiz_list.html', {'quizzes': quizzes})

@login_required
@role_required('student')
def take_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, is_published=True)
    if not quiz.course in request.user.userprofile.group.specialty.course_set.all():
        messages.error(request, "Vous n'avez pas accès à ce quiz.")
        return redirect('student_quiz_list')
    
    # Create a new attempt
    attempt = QuizAttempt.objects.create(
        quiz=quiz,
        student=request.user.userprofile,
        start_time=timezone.now()
    )
    
    questions = list(quiz.questions.all().order_by('order'))
    if quiz.randomize_questions:
        random.shuffle(questions)
    
    best_score = quiz.get_student_best_score(request.user.userprofile)
    
    return render(request, 'student/quiz/take_quiz.html', {
        'quiz': quiz,
        'questions': questions,
        'attempt': attempt,
        'best_score': best_score
    })

@login_required
@role_required('student')
def submit_quiz(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, student=request.user.userprofile)
    if attempt.end_time:
        messages.error(request, 'Ce quiz a déjà été soumis.')
        return redirect('student_quiz_list')
    
    if request.method == 'POST':
        attempt.end_time = timezone.now()
        attempt.time_spent = attempt.end_time - attempt.start_time
        
        total_points = 0
        earned_points = 0
        
        for question in attempt.quiz.questions.all():
            response = QuizResponse.objects.create(
                attempt=attempt,
                question=question
            )
            
            selected_choice_ids = request.POST.getlist(f'question_{question.id}')
            if selected_choice_ids:
                selected_choices = QuizChoice.objects.filter(id__in=selected_choice_ids)
                response.selected_choices.set(selected_choices)
                points = question.check_answer(selected_choices)
                earned_points += points
            
            total_points += question.points
        
        attempt.score = (earned_points / total_points * 100) if total_points > 0 else 0
        attempt.status = 'completed'
        attempt.save()
        
        messages.success(request, f'Quiz terminé! Votre score: {attempt.score:.1f}%')
        return redirect('quiz_results', attempt_id=attempt.id)
    
    return redirect('student_quiz_list')

@login_required
@role_required('student')
def quiz_results(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, student=request.user.userprofile)
    if not attempt.end_time:
        return redirect('take_quiz', quiz_id=attempt.quiz.id)
    
    responses = attempt.responses.all().select_related('question').prefetch_related('selected_choices', 'question__choices')
    
    return render(request, 'student/quiz/quiz_results.html', {
        'attempt': attempt,
        'responses': responses
    })