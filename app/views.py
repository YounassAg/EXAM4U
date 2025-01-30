from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction, IntegrityError
from django.core.exceptions import PermissionDenied
from django.utils.timezone import now
from django.db.models import Avg, Count, F, Q, DurationField, ExpressionWrapper, DecimalField
from django.db.models.functions import Cast
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.decorators import login_required
from .forms import UserRegistrationForm, LoginForm, ExamForm, QuizChoiceFormSet
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
    groups = Group.objects.filter(specialty_id=specialty_id).values('id', 'group_code', 'start_year', 'end_year')
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
            'description': f"{completion.student.user.first_name.upper()} {completion.student.user.last_name.upper()} {completion.exam.title} | {completion.type}",
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
    # Get the student's profile
    student_profile = UserProfile.objects.get(user=request.user)
    
    # Get completed exams
    completed_exams = ExamAttempt.objects.filter(student=student_profile, status='completed').count()
    
    # Get recent activity (last 5 exam attempts)
    recent_activity = ExamAttempt.objects.filter(student=student_profile).order_by('-start_date')[:5]
    
    # Prepare recent activity data for the template
    recent_activity_data = []
    for attempt in recent_activity:
        recent_activity_data.append({
            'title': f"Tentative pour {attempt.exam.title}",
            'date': attempt.start_date.strftime("%Y-%m-%d %H:%M"),
            'icon': 'exam'  # Assuming you have an 'exam' icon in your icons.html
        })
    
    # Get grades distribution for charts
    grades_distribution = ExamAttempt.objects.filter(
        student=student_profile,
        status='completed',
        grade__isnull=False
    ).values('exam__title').annotate(
        grade_avg=Avg('grade'),
        attempts_count=Count('id')
    ).order_by('exam__title')
    
    # Prepare data for the grades distribution chart
    grades_labels = [exam['exam__title'] for exam in grades_distribution]
    grades_data = [exam['grade_avg'] for exam in grades_distribution]
    
    # Get performance trends (grades over time)
    performance_trends = ExamAttempt.objects.filter(
        student=student_profile,
        status='completed',
        grade__isnull=False
    ).order_by('start_date').values('start_date', 'grade')
    
    # Prepare data for the performance trends chart
    trends_labels = [trend['start_date'].strftime("%Y-%m-%d") for trend in performance_trends]
    trends_data = [trend['grade'] for trend in performance_trends]
    
    context = {
        'completed_exams': completed_exams,
        'recent_activity': recent_activity_data,
        'grades_labels': grades_labels,
        'grades_data': grades_data,
        'trends_labels': trends_labels,
        'trends_data': trends_data,
    }
    
    return render(request, 'student/dashboard.html', context)


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
def teacher_exam_list(request):
    teacher_profile = request.user.userprofile
    
    # Base queryset
    exams = Exam.objects.filter(course__teacher=teacher_profile)
    
    # Get filter parameters from request
    search_query = request.GET.get('search', '').strip()
    group_filter = request.GET.get('group', '')
    exam_type = request.GET.get('exam_type', '')
    course_filter = request.GET.get('course', '')
    status_filter = request.GET.get('status', '')
    
    # Apply search filter
    if search_query:
        exams = exams.filter(
            Q(title__icontains=search_query) |
            Q(course__title__icontains=search_query) |
            Q(group__group_code__icontains=search_query)
        )
    
    # Apply group filter
    if group_filter:
        exams = exams.filter(group__group_code=group_filter)
    
    # Apply exam type filter
    if exam_type:
        exams = exams.filter(examattempt__type=exam_type).distinct()
    
    # Apply course filter
    if course_filter:
        exams = exams.filter(course__id=course_filter)
    
    # Apply status filter
    now = timezone.now()
    if status_filter:
        if status_filter == 'upcoming':
            exams = exams.filter(start_date__gt=now)
        elif status_filter == 'in_progress':
            exams = exams.filter(start_date__lte=now, end_date__gte=now)
        elif status_filter == 'completed':
            exams = exams.filter(end_date__lt=now)
    
    # Order by start date
    exams = exams.order_by('-start_date')
    
    # Get unique values for filter dropdowns
    groups = Group.objects.filter(
        id__in=Exam.objects.filter(
            course__teacher=teacher_profile
        ).values_list('group', flat=True)
    ).distinct()
    
    courses = Course.objects.filter(teacher=teacher_profile)
    
    # Status choices for filter
    status_choices = [
        ('upcoming', 'À venir'),
        ('in_progress', 'En cours'),
        ('completed', 'Terminé')
    ]
    
    # Get active filters for display
    active_filters = []
    if group_filter:
        group_obj = groups.filter(group_code=group_filter).first()
        if group_obj:
            active_filters.append({
                'type': 'group',
                'value': group_filter,
                'display': group_obj.group_code
            })
    
    if exam_type:
        exam_type_display = dict(ExamAttempt.EXAM_TYPE_CHOICES).get(exam_type, exam_type)
        active_filters.append({
            'type': 'exam_type',
            'value': exam_type,
            'display': exam_type_display
        })
    
    if course_filter:
        course_obj = courses.filter(id=course_filter).first()
        if course_obj:
            active_filters.append({
                'type': 'course',
                'value': course_filter,
                'display': course_obj.title
            })
            
    if status_filter:
        status_display = dict(status_choices).get(status_filter, status_filter)
        active_filters.append({
            'type': 'status',
            'value': status_filter,
            'display': status_display
        })

    context = {
        'exams': exams,
        'groups': groups,
        'courses': courses,
        'exam_types': ExamAttempt.EXAM_TYPE_CHOICES,
        'status_choices': status_choices,
        'active_filters': active_filters,
        'search_query': search_query,
        'selected_group': group_filter,
        'selected_exam_type': exam_type,
        'selected_course': course_filter,
        'selected_status': status_filter
    }
    
    return render(request, 'teacher/exam/exam_list.html', context)

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


@login_required
@role_required('student')
def save_answer(request):
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Method not allowed'})
    
    data = json.loads(request.body)
    attempt_id = data.get('attempt_id')
    question_id = data.get('question_id')
    response_text = data.get('response_text')
    
    try:
        attempt = ExamAttempt.objects.get(id=attempt_id, student=request.user.userprofile)
        question = Question.objects.get(id=question_id, exam=attempt.exam)
        
        # Update or create the response
        Response.objects.update_or_create(
            attempt=attempt,
            question=question,
            defaults={'response_text': response_text}
        )
        
        return JsonResponse({'success': True})
    except (ExamAttempt.DoesNotExist, Question.DoesNotExist):
        return JsonResponse({'success': False, 'message': 'Invalid attempt or question'})

@login_required
@role_required('student')
def get_saved_answers(request, attempt_id):
    try:
        attempt = ExamAttempt.objects.get(id=attempt_id, student=request.user.userprofile)
        responses = Response.objects.filter(attempt=attempt).select_related('question')
        
        answers = [{
            'question_id': response.question.id,
            'question_type': response.question.question_type,
            'response_text': response.response_text
        } for response in responses]
        
        return JsonResponse({'success': True, 'answers': answers})
    except ExamAttempt.DoesNotExist:
        return JsonResponse({'success': False, 'message': 'Invalid attempt'})
    

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
def get_exam_attempts_json(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    attempts = ExamAttempt.objects.filter(exam=exam).order_by('-modified_at')  # Order by modified_at to get the latest updates first
    attempts_data = []

    for attempt in attempts:
        attempts_data.append({
            'id': attempt.id,
            'student_name': attempt.student.user.get_full_name(),
            'username': attempt.student.user.username,
            'start_date': attempt.start_date.strftime("%d/%m/%Y"),
            'status': attempt.get_status_display(),
            'type': attempt.get_type_display(),
            'grade': attempt.grade if attempt.grade else "Non noté",
            'time_taken': (attempt.end_date - attempt.start_date).total_seconds() / 60 if attempt.end_date and attempt.start_date else None,
        })

    return JsonResponse({'attempts': attempts_data})

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
            if response.question.question_type == 'MCQ':
                # Auto-calculate MCQ score using denial logic
                response_grade = response.calculate_mcq_score()
            else:
                # Manual grading for non-MCQ questions
                response_grade = float(request.POST.get(f'grade_{response.id}', 0))
            
            response.response_grade = response_grade
            response.save()
            total_points += response_grade
            total_possible_points += response.question.points
            
        final_grade = (total_points / total_possible_points * 20) if total_possible_points > 0 else 0
        attempt.grade = final_grade
        attempt.status = 'completed'
        attempt.save()
        messages.success(request, 'La correction a été enregistrée avec succès!')
        return redirect('exam_attempts', exam_id=attempt.exam.id)

    # Prepare response data for template
    responses_data = []
    for response in responses:
        # If there's an existing grade, use it as the suggested grade
        if response.response_grade is not None:
            suggested_grade = response.response_grade
        elif response.question.question_type == 'MCQ':
            # Calculate suggested grade for MCQ questions only if no existing grade
            suggested_grade = response.calculate_mcq_score()
        else:
            # For non-MCQ questions without an existing grade, default to 0
            suggested_grade = 0
        
        responses_data.append({
            'response': response,
            'suggested_grade': suggested_grade
        })

    return render(request, 'teacher/exam/correct_exam.html', {
        'attempt': attempt,
        'responses_data': responses_data,
    })

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
        # Process quiz data
        quiz = Quiz(teacher=request.user.userprofile)
        quiz.title = request.POST.get('title')
        quiz.description = request.POST.get('description')
        quiz.course_id = request.POST.get('course')
        quiz.time_limit = request.POST.get('time_limit')
        quiz.passing_score = request.POST.get('passing_score')
        quiz.is_published = request.POST.get('is_published') == 'true'
        quiz.save()

        # Process questions and choices
        question_count = int(request.POST.get('question_count', 0))
        for i in range(1, question_count + 1):
            question_text = request.POST.get(f'question_text_{i}')
            if question_text:
                # Create question
                question = QuizQuestion(
                    quiz=quiz,
                    question_text=question_text,
                    points=float(request.POST.get(f'question_points_{i}', 1.0)),
                    order=i
                )
                question.save()

                # Process choices for this question
                choice_count = int(request.POST.get(f'choice_count_{i}', 0))
                for j in range(1, choice_count + 1):
                    choice_text = request.POST.get(f'choice_text_{i}_{j}')
                    if choice_text:
                        QuizChoice.objects.create(
                            question=question,
                            choice_text=choice_text,
                            is_correct=request.POST.get(f'choice_correct_{i}_{j}') == 'on',
                            order=j
                        )

        messages.success(request, 'Quiz créé avec succès.')
        return redirect('teacher_quiz_list')
    else:
        courses = Course.objects.filter(teacher=request.user.userprofile)
        return render(request, 'teacher/quiz/create_quiz.html', {'courses': courses})

@login_required
@role_required('teacher')
def edit_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user.userprofile)
    courses = Course.objects.filter(teacher=request.user.userprofile).order_by('title')
    
    if request.method == 'POST':
        # Basic quiz information
        quiz.title = request.POST.get('title')
        quiz.description = request.POST.get('description')
        quiz.course_id = request.POST.get('course')
        quiz.time_limit = request.POST.get('time_limit')
        quiz.passing_score = request.POST.get('passing_score')
        quiz.is_published = 'is_published' in request.POST
        
        try:
            with transaction.atomic():
                quiz.save()
                
                # Get the total number of questions
                question_count = int(request.POST.get('question_count', 0))
                
                # Process each question
                existing_questions = set(quiz.questions.values_list('id', flat=True))
                processed_questions = set()
                
                for i in range(1, question_count + 1):
                    question_text = request.POST.get(f'question_text_{i}')
                    if not question_text:
                        continue
                        
                    question_points = float(request.POST.get(f'question_points_{i}', 1.0))
                    
                    # Create or update question
                    question_id = request.POST.get(f'question_id_{i}')
                    if question_id and question_id.isdigit():
                        question = QuizQuestion.objects.get(id=int(question_id))
                        processed_questions.add(question.id)
                    else:
                        question = QuizQuestion(quiz=quiz)
                    
                    question.question_text = question_text
                    question.points = question_points
                    question.order = i
                    question.save()
                    
                    # Process choices for this question
                    choice_count = int(request.POST.get(f'choice_count_{i}', 0))
                    existing_choices = set(question.choices.values_list('id', flat=True))
                    processed_choices = set()
                    
                    for j in range(1, choice_count + 1):
                        choice_text = request.POST.get(f'choice_text_{i}_{j}')
                        if not choice_text:
                            continue
                            
                        is_correct = f'choice_correct_{i}_{j}' in request.POST
                        
                        # Create or update choice
                        choice_id = request.POST.get(f'choice_id_{i}_{j}')
                        if choice_id and choice_id.isdigit():
                            choice = QuizChoice.objects.get(id=int(choice_id))
                            processed_choices.add(choice.id)
                        else:
                            choice = QuizChoice(question=question)
                        
                        choice.choice_text = choice_text
                        choice.is_correct = is_correct
                        choice.order = j
                        choice.save()
                    
                    # Delete unprocessed choices
                    question.choices.exclude(id__in=processed_choices).delete()
                
                # Delete unprocessed questions
                quiz.questions.exclude(id__in=processed_questions).delete()
                
                messages.success(request, 'Quiz modifié avec succès.')
                return redirect('teacher_quiz_list')
                
        except Exception as e:
            messages.error(request, f'Une erreur est survenue lors de la modification du quiz: {str(e)}')
            return redirect('edit_quiz', quiz_id=quiz.id)
    
    context = {
        'quiz': quiz,
        'courses': courses,
    }
    return render(request, 'teacher/quiz/edit_quiz.html', context)

@login_required
@role_required('teacher')
def delete_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user.userprofile)
    if request.method == 'POST':
        quiz.delete()
        messages.success(request, 'Quiz supprimé avec succès!')
        return redirect('teacher_quiz_list')
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
    
    # Check if student has an incomplete attempt
    existing_attempt = QuizAttempt.objects.filter(
        quiz=quiz,
        student=request.user.userprofile,
        status='in_progress'
    ).first()
    
    if existing_attempt:
        # Check if time has expired
        if existing_attempt.is_time_expired():
            existing_attempt.status = 'timed_out'
            existing_attempt.end_time = timezone.now()
            existing_attempt.update_time_spent()
            existing_attempt.save()
            messages.error(request, 'Le temps imparti est dépassé. Votre tentative a été automatiquement soumise.')
            return redirect('quiz_results', attempt_id=existing_attempt.id)
        
        # Continue with existing attempt
        remaining_time = existing_attempt.get_remaining_time()
        if remaining_time:
            remaining_seconds = int(remaining_time.total_seconds())
        else:
            remaining_seconds = None
    else:
        # Create new attempt
        existing_attempt = QuizAttempt.objects.create(
            quiz=quiz,
            student=request.user.userprofile,
            start_time=timezone.now()
        )
        remaining_seconds = quiz.time_limit * 60 if quiz.time_limit else None
    
    # Get student statistics safely
    stats = quiz.get_student_statistics(request.user.userprofile)
    best_score = stats['best_score'] if stats is not None else None
    
    context = {
        'quiz': quiz,
        'attempt': existing_attempt,
        'remaining_seconds': remaining_seconds,
        'best_score': best_score
    }
    
    return render(request, 'student/quiz/take_quiz.html', context)

@login_required
@role_required('student')
def submit_quiz(request, attempt_id):
    attempt = get_object_or_404(QuizAttempt, id=attempt_id, student=request.user.userprofile)
    
    if attempt.status == 'completed':
        messages.error(request, 'Cette tentative a déjà été soumise.')
        return redirect('quiz_results', attempt_id=attempt.id)
    
    attempt.end_time = timezone.now()
    
    # Validate submission time
    if not attempt.validate_submission_time():
        attempt.status = 'timed_out'
        attempt.save()
        messages.error(request, 'Le temps imparti est dépassé. Votre tentative a été automatiquement soumise.')
        return redirect('quiz_results', attempt_id=attempt.id)
    
    if request.method == 'POST':
        # Process responses
        for question in attempt.quiz.questions.all():
            selected_choice_ids = request.POST.getlist(f'question_{question.id}')
            selected_choices = QuizChoice.objects.filter(id__in=selected_choice_ids)
            
            response = QuizResponse.objects.create(
                attempt=attempt,
                question=question
            )
            response.selected_choices.set(selected_choices)
            response.calculate_points()
        
        # Update attempt status and time
        attempt.status = 'completed'
        attempt.update_time_spent()
        attempt.calculate_score()
        attempt.save()
        
        messages.success(request, 'Quiz soumis avec succès!')
        return redirect('quiz_results', attempt_id=attempt.id)
    
    return redirect('take_quiz', quiz_id=attempt.quiz.id)

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

@login_required
@role_required('teacher')
def preview_quiz(request, quiz_id):
    quiz = get_object_or_404(Quiz, id=quiz_id, teacher=request.user.userprofile)
    questions = quiz.questions.all().order_by('order')
    
    context = {
        'quiz': quiz,
        'questions': questions,
        'is_preview': True
    }
    return render(request, 'teacher/quiz/preview_quiz.html', context)