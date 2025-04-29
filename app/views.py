# Standard library imports
import zipfile
import json
import csv
import re
from io import BytesIO
from datetime import timedelta

# Third-party imports
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction, IntegrityError
from django.db.models import Avg, Count, F, Q, Value, CharField
from django.db.models.functions import Concat
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.utils.timezone import now
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Preformatted
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage

# Local application imports
from .forms import UserRegistrationForm, LoginForm, ExamForm
from .models import Course, Group, Exam, Question, MCQChoice, UserProfile, Specialty, ExamAttempt, Response, StudentActionLog, ExamAttachment


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
    if request.user.is_authenticated:
        try:
            user_profile = request.user.userprofile
            if user_profile.role == 'teacher':
                return redirect('teacher_dashboard')
            else:
                return redirect('student_dashboard')
        except:
            # If there's an error retrieving the profile, just show the index page
            pass
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
                user_profile = UserProfile.objects.get(user=user)
                print(user_profile)
                if user_profile.role == 'student' and user_profile.is_taking_exam:
                    # Log the login attempt with device info
                    device_info = request.META.get('HTTP_USER_AGENT', 'Unknown')
                    ip_address = request.META.get('REMOTE_ADDR', 'Unknown')
                    
                    # Log the login attempt from another device
                    StudentActionLog.objects.create(
                        attempt=ExamAttempt.objects.filter(student=user_profile, status='in_progress').first(),
                        action='login_attempt',
                        details=f"Login attempt from another device. Device: {device_info}, IP: {ip_address}"
                    )
                    
                    messages.error(request, 'Vous ne pouvez pas vous connecter depuis un autre appareil pendant un examen.')
                    return redirect('index')
                
                login(request, user)
                if user_profile.role == 'teacher':
                    return redirect('teacher_dashboard')
                else:
                    return redirect('student_dashboard')
    else:
        form = LoginForm()
    return render(request, 'auth/login.html', {'form': form})

def user_logout(request):
    user_profile = request.user.userprofile
    if user_profile.role == 'student' and user_profile.is_taking_exam:
        user_profile.is_taking_exam = False  # Reset the flag on logout
        user_profile.save()
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
        # Get form data for exam
        title = request.POST.get('title')
        description = request.POST.get('description')
        course_id = request.POST.get('course')
        group_id = request.POST.get('group')
        duration = request.POST.get('duration')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        # Create exam instance
        exam = Exam.objects.create(
            title=title,
            description=description,
            course_id=course_id,
            group_id=group_id,
            duration=duration,
            start_date=start_date,
            end_date=end_date
        )

        # Handle exam attachments
        if request.FILES:
            exam_attachment_files = request.FILES.getlist('exam_attachment_file[]')
            exam_attachment_types = request.POST.getlist('exam_attachment_type[]')
            exam_attachment_titles = request.POST.getlist('exam_attachment_title[]')
            exam_attachment_descriptions = request.POST.getlist('exam_attachment_description[]')

            for i, file in enumerate(exam_attachment_files):
                if file:  # Only process if a file was actually uploaded
                    attachment_type = exam_attachment_types[i] if i < len(exam_attachment_types) else 'other'
                    attachment_title = exam_attachment_titles[i] if i < len(exam_attachment_titles) else ''
                    attachment_description = exam_attachment_descriptions[i] if i < len(exam_attachment_descriptions) else ''
                    
                    ExamAttachment.objects.create(
                        exam=exam,
                        file=file,
                        file_type=attachment_type,
                        title=attachment_title,
                        description=attachment_description
                    )

        # Process questions
        question_count = int(request.POST.get('question_count', 0))
        for i in range(1, question_count + 1):
            question_type = request.POST.get(f'question_type_{i}')
            question_wording = request.POST.get(f'question_wording_{i}')
            question_points = request.POST.get(f'question_points_{i}')
            
            # Skip if essential data is missing
            if not question_type or not question_wording or not question_points:
                continue
                
            try:
                # Create question with safe conversion to float
                question = Question.objects.create(
                    exam=exam,
                    question_type=question_type,
                    wording=question_wording,
                    points=float(question_points)
                )
            except (ValueError, TypeError):
                # If conversion fails, use default value of 1.0
                question = Question.objects.create(
                    exam=exam,
                    question_type=question_type,
                    wording=question_wording,
                    points=1.0
                )

            # Handle question attachments
            question_attachment_files = request.FILES.getlist(f'question_{i}_attachment_file[]')
            question_attachment_types = request.POST.getlist(f'question_{i}_attachment_type[]')
            question_attachment_titles = request.POST.getlist(f'question_{i}_attachment_title[]')
            question_attachment_descriptions = request.POST.getlist(f'question_{i}_attachment_description[]')

            for j, file in enumerate(question_attachment_files):
                if file:  # Only process if a file was actually uploaded
                    attachment_type = question_attachment_types[j] if j < len(question_attachment_types) else 'other'
                    attachment_title = question_attachment_titles[j] if j < len(question_attachment_titles) else ''
                    attachment_description = question_attachment_descriptions[j] if j < len(question_attachment_descriptions) else ''
                    
                    ExamAttachment.objects.create(
                        question=question,
                        file=file,
                        file_type=attachment_type,
                        title=attachment_title,
                        description=attachment_description
                    )
            
            # If MCQ question, create choices
            if question_type == 'MCQ':
                try:
                    mcq_choice_count = int(request.POST.get(f'mcq_choice_count_{i}', 0))
                except (ValueError, TypeError):
                    mcq_choice_count = 0
                    
                has_correct_choice = False
                
                for j in range(1, mcq_choice_count + 1):
                    choice_text = request.POST.get(f'mcq_choice_text_{i}_{j}')
                    is_correct = request.POST.get(f'mcq_choice_correct_{i}_{j}') == 'on'
                    
                    # Skip if choice text is missing
                    if not choice_text:
                        continue
                        
                    if is_correct:
                        has_correct_choice = True
                    
                    MCQChoice.objects.create(
                        question=question,
                        choice_label=choice_text,
                        is_correct=is_correct
                    )
                
                # If multiple choices are correct, set question to allow multiple answers
                if mcq_choice_count > 0:
                    correct_choices = MCQChoice.objects.filter(question=question, is_correct=True).count()
                    if correct_choices > 1:
                        question.allow_multiple_answers = True
                        question.save()
        
        return redirect('teacher_exam_list')
    
    else:
        courses = Course.objects.filter(teacher=request.user.userprofile)
        groups = Group.objects.all()
        return render(request, 'teacher/exam/create_exam.html', {
            'courses': courses,
            'groups': groups
        })


@login_required
@role_required('teacher')
def edit_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    
    # Ensure the teacher owns this exam
    if exam.course.teacher != request.user.userprofile:
        return redirect('teacher_exam_list')
    
    if request.method == 'POST':
        # Update exam data
        exam.title = request.POST.get('title')
        exam.description = request.POST.get('description')
        exam.course_id = request.POST.get('course')
        exam.group_id = request.POST.get('group')
        exam.duration = request.POST.get('duration')
        exam.start_date = request.POST.get('start_date')
        exam.end_date = request.POST.get('end_date')
        exam.save()
        
        # Handle attachment deletions first
        # Delete exam attachments marked for deletion
        for key in request.POST:
            if key.startswith('delete_attachment_'):
                attachment_id = key.split('_')[-1]
                try:
                    attachment = ExamAttachment.objects.get(id=attachment_id)
                    if attachment.exam == exam and attachment.question is None:
                        attachment.delete()
                except ExamAttachment.DoesNotExist:
                    pass

        # Delete question attachments marked for deletion
        for key in request.POST:
            if key.startswith('delete_question_attachment_'):
                attachment_id = key.split('_')[-1]
                try:
                    attachment = ExamAttachment.objects.get(id=attachment_id)
                    if attachment.question and attachment.question.exam == exam:
                        attachment.delete()
                except ExamAttachment.DoesNotExist:
                    pass
        
        # Handle exam attachments
        if request.FILES:
            # Add new attachments
            exam_attachment_files = request.FILES.getlist('exam_attachment_file[]')
            exam_attachment_types = request.POST.getlist('exam_attachment_type[]')
            exam_attachment_titles = request.POST.getlist('exam_attachment_title[]')
            exam_attachment_descriptions = request.POST.getlist('exam_attachment_description[]')

            for i, file in enumerate(exam_attachment_files):
                if file:  # Only process if a file was actually uploaded
                    attachment_type = exam_attachment_types[i] if i < len(exam_attachment_types) else 'other'
                    attachment_title = exam_attachment_titles[i] if i < len(exam_attachment_titles) else ''
                    attachment_description = exam_attachment_descriptions[i] if i < len(exam_attachment_descriptions) else ''
                    
                    ExamAttachment.objects.create(
                        exam=exam,
                        file=file,
                        file_type=attachment_type,
                        title=attachment_title,
                        description=attachment_description
                    )
        
        # Get all existing questions
        existing_questions = list(exam.question_set.all())
        existing_question_ids = [str(q.id) for q in existing_questions]
        
        # Track which questions have been processed
        processed_question_ids = []
        
        # Process existing questions
        for question_index in range(1, 100):  # Use a reasonable upper limit
            question_id = request.POST.get(f'question_id_{question_index}')
            
            # Skip if no question ID for this index (means there's no question at this position)
            if not question_id:
                continue
                
            if question_id == 'new':
                # This is a new question, process it later
                continue
                
            # Mark this question as processed
            processed_question_ids.append(question_id)
            
            # Get the existing question
            try:
                question = Question.objects.get(id=question_id)
            except Question.DoesNotExist:
                continue
                
            # Only update if it belongs to this exam
            if question.exam != exam:
                continue
            
            # Get updated question data
            q_type = request.POST.get(f'question_type_{question_index}')
            q_wording = request.POST.get(f'question_wording_{question_index}')
            q_points = request.POST.get(f'question_points_{question_index}')
            
            # Only update if we have valid data
            if not q_type or not q_wording:
                continue
                
            try:
                # Update question with safe conversion to float
                question.question_type = q_type
                question.wording = q_wording
                question.points = float(q_points)
                question.save()
            except (ValueError, TypeError):
                # If conversion fails, use default value of 1.0
                question.question_type = q_type
                question.wording = q_wording
                question.points = 1.0
                question.save()
            
            # Handle question attachments
            if request.FILES:
                # Add new attachments
                question_attachment_files = request.FILES.getlist(f'question_{question_index}_attachment_file[]')
                question_attachment_types = request.POST.getlist(f'question_{question_index}_attachment_type[]')
                question_attachment_titles = request.POST.getlist(f'question_{question_index}_attachment_title[]')
                question_attachment_descriptions = request.POST.getlist(f'question_{question_index}_attachment_description[]')

                for j, file in enumerate(question_attachment_files):
                    if file:  # Only process if a file was actually uploaded
                        attachment_type = question_attachment_types[j] if j < len(question_attachment_types) else 'other'
                        attachment_title = question_attachment_titles[j] if j < len(question_attachment_titles) else ''
                        attachment_description = question_attachment_descriptions[j] if j < len(question_attachment_descriptions) else ''
                        
                        ExamAttachment.objects.create(
                            question=question,
                            file=file,
                            file_type=attachment_type,
                            title=attachment_title,
                            description=attachment_description
                        )
            
            # If MCQ question, update choices
            if question.question_type == 'MCQ':
                # Delete existing choices
                question.mcqchoice_set.all().delete()
                
                # Add new choices
                try:
                    mcq_choice_count = int(request.POST.get(f'mcq_choice_count_{question_index}', 0))
                except (ValueError, TypeError):
                    mcq_choice_count = 0
                    
                has_correct_choice = False
                
                for j in range(1, mcq_choice_count + 1):
                    choice_text = request.POST.get(f'mcq_choice_text_{question_index}_{j}')
                    is_correct = request.POST.get(f'mcq_choice_correct_{question_index}_{j}') == 'on'
                    
                    # Skip if choice text is missing
                    if not choice_text:
                        continue
                        
                    if is_correct:
                        has_correct_choice = True
                    
                    MCQChoice.objects.create(
                        question=question,
                        choice_label=choice_text,
                        is_correct=is_correct
                    )
                
                # If multiple choices are correct, set question to allow multiple answers
                if mcq_choice_count > 0:
                    correct_choices = MCQChoice.objects.filter(question=question, is_correct=True).count()
                    if correct_choices > 1:
                        question.allow_multiple_answers = True
                        question.save()
        
        # Delete questions that were not processed (removed from form)
        for q in existing_questions:
            if str(q.id) not in processed_question_ids:
                q.delete()
        
        # Process new questions
        try:
            new_question_count = int(request.POST.get('question_count', 0))
        except (ValueError, TypeError):
            new_question_count = 0
            
        existing_question_count = len(processed_question_ids)
        
        # Only process indices greater than the existing question count
        for i in range(1, new_question_count + 1):
            # Check if this is a new question (not an existing one)
            question_id = request.POST.get(f'question_id_{i}')
            if question_id != 'new':
                continue
                
            question_type = request.POST.get(f'question_type_{i}')
            question_wording = request.POST.get(f'question_wording_{i}')
            question_points = request.POST.get(f'question_points_{i}')
            
            # Skip if essential data is missing
            if not question_type or not question_wording:
                continue
                
            try:
                # Create new question with safe conversion to float
                question = Question.objects.create(
                    exam=exam,
                    question_type=question_type,
                    wording=question_wording,
                    points=float(question_points or 0)
                )
            except (ValueError, TypeError):
                # If conversion fails, use default value of 1.0
                question = Question.objects.create(
                    exam=exam,
                    question_type=question_type,
                    wording=question_wording,
                    points=1.0
                )
                
            # Handle question attachments
            if request.FILES:
                # Add new attachments
                question_attachment_files = request.FILES.getlist(f'question_{i}_attachment_file[]')
                question_attachment_types = request.POST.getlist(f'question_{i}_attachment_type[]')
                question_attachment_titles = request.POST.getlist(f'question_{i}_attachment_title[]')
                question_attachment_descriptions = request.POST.getlist(f'question_{i}_attachment_description[]')

                for j, file in enumerate(question_attachment_files):
                    if file:  # Only process if a file was actually uploaded
                        attachment_type = question_attachment_types[j] if j < len(question_attachment_types) else 'other'
                        attachment_title = question_attachment_titles[j] if j < len(question_attachment_titles) else ''
                        attachment_description = question_attachment_descriptions[j] if j < len(question_attachment_descriptions) else ''
                        
                        ExamAttachment.objects.create(
                            question=question,
                            file=file,
                            file_type=attachment_type,
                            title=attachment_title,
                            description=attachment_description
                        )
                
            # If MCQ question, create choices
            if question_type == 'MCQ':
                try:
                    mcq_choice_count = int(request.POST.get(f'mcq_choice_count_{i}', 0))
                except (ValueError, TypeError):
                    mcq_choice_count = 0
                    
                has_correct_choice = False
                
                for j in range(1, mcq_choice_count + 1):
                    choice_text = request.POST.get(f'mcq_choice_text_{i}_{j}')
                    is_correct = request.POST.get(f'mcq_choice_correct_{i}_{j}') == 'on'
                    
                    # Skip if choice text is missing
                    if not choice_text:
                        continue
                        
                    if is_correct:
                        has_correct_choice = True
                    
                    MCQChoice.objects.create(
                        question=question,
                        choice_label=choice_text,
                        is_correct=is_correct
                    )
                
                # If multiple choices are correct, set question to allow multiple answers
                if mcq_choice_count > 0:
                    correct_choices = MCQChoice.objects.filter(question=question, is_correct=True).count()
                    if correct_choices > 1:
                        question.allow_multiple_answers = True
                        question.save()
        
        return redirect('teacher_exam_list')
    
    else:
        courses = Course.objects.filter(teacher=request.user.userprofile)
        groups = Group.objects.all()
        return render(request, 'teacher/exam/edit_exam.html', {
            'exam': exam,
            'courses': courses,
            'groups': groups
        })


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

    # Pagination
    per_page = request.GET.get('per_page', 12)  # Default to 12 items per page
    try:
        per_page = int(per_page)
        if per_page not in [6, 12, 24, 48]:  # Validate per_page value
            per_page = 12  # Default to 12 if invalid value
    except ValueError:
        per_page = 12
        
    paginator = Paginator(exams, per_page)
    page_number = request.GET.get('page', 1)
    
    try:
        paginated_exams = paginator.page(page_number)
    except PageNotAnInteger:
        # If page is not an integer, deliver first page
        paginated_exams = paginator.page(1)
    except EmptyPage:
        # If page is out of range, deliver last page
        paginated_exams = paginator.page(paginator.num_pages)

    context = {
        'exams': paginated_exams,
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
            if status == 'abandoned':
                student = request.user.userprofile
                student.is_taking_exam = False  # Reset the flag if the exam is abandoned
                student.save()
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

    # Check if the student has any completed or abandoned attempts
    existing_completed_or_abandoned_attempts = ExamAttempt.objects.filter(
        exam=exam, 
        student=student, 
        status__in=['completed', 'abandoned']
    ).exists()

    if existing_completed_or_abandoned_attempts:
        messages.error(request, "Vous avez déjà terminé ou abandonné cet examen.")
        return redirect('student_exam_list')

    # Check if there's an in-progress attempt
    attempt = ExamAttempt.objects.filter(
        exam=exam, 
        student=student, 
        status__in=['in_progress']
    ).first()

    if not attempt:
        # Create a new attempt if there's no in-progress attempt
        attempt = ExamAttempt.objects.create(
            exam=exam, 
            student=student, 
            status='in_progress', 
            start_date=timezone.now()
        )
        # Set the is_taking_exam flag to True
        student.is_taking_exam = True
        student.save()

    questions = Question.objects.filter(exam=exam).prefetch_related('mcqchoice_set')

    if request.method == 'POST':
        form = ExamForm(request.POST, questions=questions)
        if form.is_valid():
            for question in questions:
                # Prepare the response text based on question type
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
                
                # Update existing response or create new one
                Response.objects.update_or_create(
                    attempt=attempt,
                    question=question,
                    defaults={'response_text': response_text}
                )
            
            # Mark attempt as completed
            attempt.status = 'completed'
            attempt.end_date = timezone.now()
            attempt.save()
            
            # Reset the is_taking_exam flag
            student.is_taking_exam = False
            student.save()
            
            return render(request, 'student/exam/exam_completed.html')
    else:
        # Load existing responses for initial form data
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
@role_required('teacher')
def mark_all_attempts_completed(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    
    # Get all in-progress attempts for this exam
    in_progress_attempts = ExamAttempt.objects.filter(exam=exam, status='in_progress')
    
    # Mark all in-progress attempts as completed
    for attempt in in_progress_attempts:
        attempt.status = 'completed'
        attempt.save()
        
        # Reset the is_taking_exam flag for the student
        student = attempt.student
        student.is_taking_exam = False
        student.save()
    
    messages.success(request, "Toutes les tentatives en cours ont été marquées comme terminées.")
    return redirect('exam_attempts', exam_id=exam.id)


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
    
    # Pre-filter logs by category with exact action types from JavaScript
    suspicious_logs = logs.filter(action__in=[
        'Focus lost',  # Window/tab focus changes
        'Network disconnect',  # Network issues
        'Network reconnect',
        'Extended disconnect',
        'login_attempt',  # Login attempts from other devices
    ])
    
    # Calculate durations for suspicious activities
    suspicious_logs_with_duration = []
    focus_lost_start = None
    network_disconnect_start = None
    
    for log in suspicious_logs:
        if log.action == 'Focus lost':
            focus_lost_start = log.timestamp
            # Find the next focus gain by looking at the next log entry
            next_focus = logs.filter(timestamp__gt=log.timestamp).first()
            if next_focus:
                duration = (next_focus.timestamp - log.timestamp).total_seconds()
                log.duration = int(duration)
                suspicious_logs_with_duration.append(log)
        elif log.action == 'Network disconnect':
            network_disconnect_start = log.timestamp
        elif log.action == 'Network reconnect' and network_disconnect_start:
            duration = (log.timestamp - network_disconnect_start).total_seconds()
            log.duration = int(duration)
            network_disconnect_start = None
            suspicious_logs_with_duration.append(log)
        elif log.action == 'Extended disconnect':
            # Extended disconnect already includes duration in its details
            suspicious_logs_with_duration.append(log)
        elif log.action == 'login_attempt':
            suspicious_logs_with_duration.append(log)
    
    # Other activities (everything else)
    other_logs = logs.filter(action__in=[
        'Suspicious shortcut',
        'Copy attempt',
        'Screen resize',
        'Context menu',
        'Dev tools',
        'Mouse leave',
        'Text selection',
        'question_answered',
        'inactivity_detected'
    ])
    
    return render(request, 'teacher/exam/exam_logs.html', {
        'attempt': attempt,
        'logs': logs,
        'suspicious_logs': suspicious_logs_with_duration,
        'other_logs': other_logs,
    })


# @login_required
# @role_required('teacher')
# def rattrapage_exam(request, exam_id):
#     exam = get_object_or_404(Exam, id=exam_id)
#     students = UserProfile.objects.filter(group=exam.group, role='student')
#     if request.method == 'POST':
#         selected_students = request.POST.getlist('students')
#         for student_id in selected_students:
#             student = UserProfile.objects.get(id=student_id)
#             ExamAttempt.objects.create(
#                 exam=exam,
#                 student=student,
#                 type='rattrapage'
#             )
#             messages.success(request, f"Exam attempt created for {student.first_name} {student.last_name}.")
#         return redirect('teacher_exam_list')
#     return render(request, 'teacher/exam/rattrapage_exam.html', {
#         'exam': exam,
#         'students': students
#     })


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
    
    # Calculate statistics
    total_students = exam.group.userprofile_set.filter(role='student').count()
    completed_attempts = attempts.filter(status='completed').count()
    in_progress_attempts = attempts.filter(status='in_progress').count()
    
    context = {
        'exam': exam,
        'attempts': attempts,
        'total_students': total_students,
        'completed_attempts': completed_attempts,
        'in_progress_attempts': in_progress_attempts,
    }
    
    return render(request, 'teacher/exam/exam_attempts.html', context)


@csrf_exempt
def reset_is_taking_exam(request, username):
    if request.method == 'POST':
        try:
            user = User.objects.get(username=username)
            user_profile = UserProfile.objects.get(user=user)
            user_profile.is_taking_exam = False
            user_profile.save()
            return JsonResponse({'success': True})
        except User.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'User not found'}, status=404)
        except UserProfile.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'UserProfile not found'}, status=404)
    return JsonResponse({'success': False, 'error': 'Invalid request method'}, status=400)


@login_required
@role_required('teacher')
def get_exam_attempts_json(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    attempts = ExamAttempt.objects.filter(exam=exam).order_by('-modified_at')
    attempts_data = []

    for attempt in attempts:
        print(f"Processing attempt {attempt.id}:")
        print(f"- Raw status: {attempt.status}")
        print(f"- Status display: {attempt.get_status_display()}")
        
        attempt_data = {
            'id': attempt.id,
            'student_name': attempt.student.user.get_full_name(),
            'username': attempt.student.user.username,
            'start_date': attempt.start_date.strftime("%d/%m/%Y"),
            'status': attempt.status,  # Raw status value for conditional logic
            'status_display': attempt.get_status_display(),  # Translated status text
            'type': attempt.get_type_display(),
            'grade': attempt.grade if attempt.grade else None,
            'time_taken': (attempt.end_date - attempt.start_date).total_seconds() / 60 if attempt.end_date and attempt.start_date else None,
        }
        print(f"- Data being sent: {attempt_data}")
        attempts_data.append(attempt_data)
    
    # Calculate statistics for the response
    total_students = exam.group.userprofile_set.filter(role='student').count()
    completed_attempts = attempts.filter(status='completed').count()
    in_progress_attempts = attempts.filter(status='in_progress').count()
    
    stats_data = {
        'total_students': total_students,
        'completed_attempts': completed_attempts,
        'in_progress_attempts': in_progress_attempts,
    }

    return JsonResponse({'attempts': attempts_data, 'stats': stats_data})

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
                if f'grade_{response.id}' in request.POST and request.POST[f'grade_{response.id}']:
                    response_grade = float(request.POST.get(f'grade_{response.id}', 0))

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
                    question_text = f"Question {i}: \n {response.question.wording}"
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
                    question_score = response_obj.response_grade if response_obj and response_obj.response_grade is not None else 0
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
                    question_score = response_obj.response_grade if response_obj and response_obj.response_grade is not None else 0
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
        spaceAfter=12,
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


@login_required
@role_required('student')
def exam_rules(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    return render(request, 'student/exam/exam_rules.html', {'exam': exam})

def custom_403(request, exception):
    return render(request, 'errors/403.html', status=403)


def custom_404(request, exception):
    return render(request, 'errors/404.html', status=404)

@login_required
@role_required('teacher')
def teacher_settings(request):
    """Main settings page for teachers"""
    return render(request, 'teacher/settings/index.html')


@login_required
@role_required('teacher')
def teacher_backup_database(request):
    """Database backup functionality for teachers"""
    import os
    import datetime
    from django.http import HttpResponse
    from django.conf import settings
    from django.contrib import messages
    
    if request.method == 'POST':
        try:
            # Create a timestamp for the backup file
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_file = f'exam4u_backup_{timestamp}.json'
            
            # Use Django's dumpdata management command to create a backup
            from django.core.management import call_command
            from io import StringIO
            
            output = StringIO()
            call_command('dumpdata', 
                        exclude=['contenttypes', 'auth.permission', 'admin.logentry', 'sessions.session'],
                        natural_foreign=True, 
                        indent=2, 
                        stdout=output)
            
            # Create the response with the backup data
            response = HttpResponse(output.getvalue(), content_type='application/json')
            response['Content-Disposition'] = f'attachment; filename="{backup_file}"'
            
            # Log the backup action
            messages.success(request, 'Sauvegarde de la base de données effectuée avec succès.')
            return response
            
        except Exception as e:
            messages.error(request, f'Erreur lors de la sauvegarde de la base de données: {str(e)}')
            return redirect('teacher_settings')
    
    return render(request, 'teacher/settings/backup.html')


@login_required
@role_required('teacher')
def teacher_restore_database(request):
    """Database restore functionality for teachers"""
    from django.contrib import messages
    
    if request.method == 'POST' and request.FILES.get('backup_file'):
        try:
            backup_file = request.FILES['backup_file']
            # Validate the file is a JSON file
            if not backup_file.name.endswith('.json'):
                messages.error(request, 'Le fichier doit être au format JSON.')
                return redirect('teacher_restore_database')
                
            # Use Django's loaddata management command to restore the backup
            from django.core.management import call_command
            from tempfile import NamedTemporaryFile
            
            with NamedTemporaryFile(suffix='.json', delete=False) as temp_file:
                for chunk in backup_file.chunks():
                    temp_file.write(chunk)
                temp_file_path = temp_file.name
                
            # Execute the loaddata command
            call_command('loaddata', temp_file_path)
            
            # Clean up the temporary file
            import os
            os.unlink(temp_file_path)
            
            messages.success(request, 'Restauration de la base de données effectuée avec succès.')
            
        except Exception as e:
            messages.error(request, f'Erreur lors de la restauration de la base de données: {str(e)}')
            
    return render(request, 'teacher/settings/restore.html')


@login_required
@role_required('teacher')
def teacher_theme_settings(request):
    """Theme settings for teachers"""
    from django.contrib import messages
    
    if request.method == 'POST':
        theme = request.POST.get('theme', 'light')
        # Store theme preference in the session
        request.session['theme'] = theme
        messages.success(request, 'Préférences de thème mises à jour avec succès.')
        
    current_theme = request.session.get('theme', 'light')
    return render(request, 'teacher/settings/theme.html', {'current_theme': current_theme})


@login_required
@role_required('teacher')
def teacher_notification_settings(request):
    """Notification settings for teachers"""
    from django.contrib import messages
    
    if request.method == 'POST':
        # Process notification settings
        email_notifications = request.POST.get('email_notifications') == 'on'
        browser_notifications = request.POST.get('browser_notifications') == 'on'
        
        # Store notification preferences in the session
        request.session['email_notifications'] = email_notifications
        request.session['browser_notifications'] = browser_notifications
        
        messages.success(request, 'Préférences de notification mises à jour avec succès.')
        
    # Get current settings
    email_notifications = request.session.get('email_notifications', True)
    browser_notifications = request.session.get('browser_notifications', True)
    
    return render(request, 'teacher/settings/notifications.html', {
        'email_notifications': email_notifications,
        'browser_notifications': browser_notifications
    })


@login_required
@role_required('teacher')
def teacher_system_info(request):
    """System information for teachers"""
    import platform
    import django
    import sys
    import os
    import psutil
    from django.db import connection
    
    # Collect system information
    system_info = {
        'python_version': platform.python_version(),
        'django_version': django.get_version(),
        'os_name': platform.system(),
        'os_version': platform.version(),
        'cpu_usage': psutil.cpu_percent(interval=1),
        'memory_usage': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent,
    }
    
    # Database stats
    cursor = connection.cursor()
    
    # Count number of records in key tables
    stats = {}
    for table in ['app_exam', 'app_question', 'app_examattempt', 'app_course', 'app_userprofile']:
        cursor.execute(f"SELECT COUNT(*) FROM {table}")
        row = cursor.fetchone()
        stats[table] = row[0] if row else 0
    
    return render(request, 'teacher/settings/system_info.html', {
        'system_info': system_info,
        'stats': stats
    })