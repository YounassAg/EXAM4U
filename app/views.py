from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction, IntegrityError
from django.db.models import Count, Avg
from django.core.exceptions import PermissionDenied
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .forms import UserRegistrationForm, LoginForm, ExamForm
from .models import Course, Group, Exam, Question, MCQChoice, UserProfile, Specialty, ExamAttempt, Response
from django.http import JsonResponse

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

@role_required('teacher')
@login_required
def teacher_dashboard(request):
    # Get teacher's profile
    teacher_profile = UserProfile.objects.get(user=request.user, role='teacher')
    
    # Get active courses (courses taught by this teacher)
    active_courses = Course.objects.filter(teacher=teacher_profile)
    
    # Get total number of students across all courses
    total_students = UserProfile.objects.filter(
        role='student',
        group__in=[exam.group for exam in Exam.objects.filter(course__teacher=teacher_profile)]
    ).distinct().count()
    
    # Get pending grading count (responses without grades)
    pending_grading = ExamAttempt.objects.filter(
        exam__course__teacher=teacher_profile,
        status='completed',
        response__response_grade__isnull=True
    ).distinct().count()
    
    # Get upcoming exams
    upcoming_exams = Exam.objects.filter(
        course__teacher=teacher_profile,
        start_date__gt=timezone.now()
    ).count()
    
    # Get course performance data
    course_performance = []
    for course in active_courses:
        exam_attempts = ExamAttempt.objects.filter(
            exam__course=course,
            status='completed',
            grade__isnull=False
        )
        average_grade = exam_attempts.aggregate(Avg('grade'))['grade__avg']
        
        if average_grade is not None:
            course_performance.append({
                'title': course.title,
                'average': round(average_grade, 1),
                'performance_class': 'emerald' if average_grade >= 10 else 'amber'
            })

    context = {
        'active_courses_count': active_courses.count(),
        'total_students': total_students,
        'pending_grading': pending_grading,
        'upcoming_exams': upcoming_exams,
        'course_performance': course_performance,
    }
    
    return render(request, 'teacher/dashboard.html', context)

@role_required('teacher')
@login_required
def teacher_courses(request):
    teacher = request.user.userprofile
    courses = Course.objects.filter(teacher=teacher)
    return render(request, 'teacher/courses/courses.html', {'courses': courses})

@role_required('student')
@login_required
def student_courses(request):
    student_specialty = request.user.userprofile.specialty
    courses = Course.objects.filter(specialty=student_specialty)
    return render(request, 'student/courses/courses.html', {'courses': courses})

@role_required('student')
@login_required
def student_dashboard(request):
    return render(request, 'student/dashboard.html')

@role_required('teacher')
@login_required
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

                question_count = int(request.POST.get('question_count', 0))
                for i in range(1, question_count + 1):
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

                    if question_type == 'MCQ':
                        choice_count = int(request.POST.get(f'mcq_choice_count_{i}', 0))
                        for j in range(1, choice_count + 1):
                            choice_label = request.POST.get(f'mcq_choice_text_{i}_{j}')
                            is_correct = request.POST.get(f'mcq_choice_correct_{i}_{j}') == 'on'
                            MCQChoice.objects.create(
                                question=question,
                                choice_label=choice_label,
                                is_correct=is_correct
                            )

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
                # Updating exam details (title, description, etc.)
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

                # Update the exam details
                exam.title = title
                exam.description = description
                exam.course = course
                exam.group = group
                exam.duration = duration
                exam.max_attempts = max_attempts
                exam.start_date = start_date
                exam.end_date = end_date
                exam.save()

                # Get the current question count from the form
                question_count = int(request.POST.get('question_count', 0))

                # Handle adding new questions, editing existing ones, and deleting questions
                for i in range(1, question_count + 1):
                    question_id = request.POST.get(f'question_id_{i}')
                    question_type = request.POST.get(f'question_type_{i}')
                    question_wording = request.POST.get(f'question_wording_{i}')
                    question_points = request.POST.get(f'question_points_{i}')

                    # Check if the question exists or if it is a new one
                    if question_id:  # Editing an existing question
                        question = Question.objects.get(id=question_id)
                        question.question_type = question_type
                        question.wording = question_wording
                        question.points = question_points
                        question.save()
                    else:  # Adding a new question
                        question = Question.objects.create(
                            exam=exam,
                            question_type=question_type,
                            wording=question_wording,
                            points=question_points,
                            allow_multiple_answers=(question_type == 'MCQ')
                        )

                    # Handle MCQ choices if the question type is MCQ
                    if question_type == 'MCQ':
                        choice_count = int(request.POST.get(f'mcq_choice_count_{i}', 0))
                        # First, delete all existing choices for this question
                        MCQChoice.objects.filter(question=question).delete()

                        for j in range(1, choice_count + 1):
                            choice_label = request.POST.get(f'mcq_choice_text_{i}_{j}')
                            is_correct = request.POST.get(f'mcq_choice_correct_{i}_{j}') == 'on'
                            MCQChoice.objects.create(
                                question=question,
                                choice_label=choice_label,
                                is_correct=is_correct
                            )

                # Handle deletion of questions
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
        # Prepopulate the form with the current exam details, including questions
        courses = Course.objects.filter(teacher__user=request.user)
        groups = Group.objects.all()

        return render(request, 'teacher/exam/edit_exam.html', {
            'exam': exam,
            'courses': courses,
            'groups': groups
        })

def edit_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # 1. Update basic exam details
                exam.title = request.POST.get('title')
                exam.description = request.POST.get('description')
                exam.course = Course.objects.get(id=request.POST.get('course'))
                exam.group = Group.objects.get(id=request.POST.get('group'))
                exam.duration = request.POST.get('duration')
                exam.max_attempts = request.POST.get('max_attempts')
                exam.start_date = request.POST.get('start_date')
                exam.end_date = request.POST.get('end_date')
                exam.save()

                # 2. Handle questions
                existing_questions = set(exam.question_set.values_list('id', flat=True))
                processed_questions = set()
                question_count = int(request.POST.get('question_count', 0))

                for i in range(1, question_count + 1):
                    question_id = request.POST.get(f'question_id_{i}')
                    question_type = request.POST.get(f'question_type_{i}')
                    question_wording = request.POST.get(f'question_wording_{i}')
                    question_points = request.POST.get(f'question_points_{i}')

                    if question_id:  # Update existing question
                        question = Question.objects.get(id=question_id)
                        processed_questions.add(int(question_id))
                        
                        question.question_type = question_type
                        question.wording = question_wording
                        question.points = question_points
                        question.allow_multiple_answers = (question_type == 'MCQ')
                        question.save()
                    else:  # Create new question
                        question = Question.objects.create(
                            exam=exam,
                            question_type=question_type,
                            wording=question_wording,
                            points=question_points,
                            allow_multiple_answers=(question_type == 'MCQ')
                        )
                        processed_questions.add(question.id)

                    # Handle MCQ choices
                    if question_type == 'MCQ':
                        # Delete existing choices
                        MCQChoice.objects.filter(question=question).delete()
                        
                        # Create new choices
                        choice_count = int(request.POST.get(f'mcq_choice_count_{i}', 0))
                        for j in range(1, choice_count + 1):
                            choice_text = request.POST.get(f'mcq_choice_text_{i}_{j}')
                            is_correct = request.POST.get(f'mcq_choice_correct_{i}_{j}') == 'on'
                            
                            if choice_text:  # Only create if there's actual text
                                MCQChoice.objects.create(
                                    question=question,
                                    choice_label=choice_text,
                                    is_correct=is_correct
                                )

                # 3. Delete questions that weren't processed (removed questions)
                questions_to_delete = existing_questions - processed_questions
                Question.objects.filter(id__in=questions_to_delete).delete()

                messages.success(request, 'Exam updated successfully!')
                return redirect('teacher_exam_list')

        except Exception as e:
            messages.error(request, f'Error updating exam: {str(e)}')
            return redirect('edit_exam', exam_id=exam_id)

    else:  # GET request
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
    

@role_required('student')
@login_required
def student_exam_list(request):
    student_group = request.user.userprofile.group
    exams = Exam.objects.filter(group=student_group)
    return render(request, 'student/exam/exam_list.html', {'exams': exams})

@role_required('teacher')
@login_required
def teacher_exam_list(request):
    teacher_profile = request.user.userprofile
    exams = Exam.objects.filter(course__teacher=teacher_profile)
    return render(request, 'teacher/exam/exam_list.html', {'exams': exams})

@role_required('student')
@login_required
def take_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    student = request.user.userprofile

    # Check if the student has already attempted this exam
    attempt = ExamAttempt.objects.filter(exam=exam, student=student, status='in_progress').first()
    if not attempt:
        attempt = ExamAttempt.objects.create(exam=exam, student=student)

    questions = Question.objects.filter(exam=exam)

    if request.method == 'POST':
        form = ExamForm(request.POST, questions=questions)
        if form.is_valid():
            for question in questions:
                if question.question_type == 'MCQ':
                    response_data = form.cleaned_data[f'question_{question.id}']
                    if question.allow_multiple_answers:
                        selected_choices = MCQChoice.objects.filter(id__in=response_data)
                        response_text = ', '.join([choice.choice_label for choice in selected_choices])
                    else:
                        selected_choice = MCQChoice.objects.get(id=response_data)
                        response_text = selected_choice.choice_label
                else:
                    response_text = form.cleaned_data[f'question_{question.id}']

                Response.objects.create(
                    attempt=attempt,
                    question=question,
                    response_text=response_text
                )
            attempt.status = 'completed'
            attempt.end_date = timezone.now()
            attempt.save()
            return redirect('exam_completed', attempt_id=attempt.id)
    else:
        form = ExamForm(questions=questions)

    return render(request, 'student/exam/take_exam.html', {'exam': exam, 'form': form})

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
def exam_attempts(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    attempts = ExamAttempt.objects.filter(exam=exam, status='completed')

    # Calculate time taken for each attempt
    for attempt in attempts:
        if attempt.end_date and attempt.start_date:
            attempt.time_taken = (attempt.end_date - attempt.start_date).total_seconds() / 60  # time taken in minutes
        else:
            attempt.time_taken = None

    context = {
        'exam': exam,
        'attempts': attempts
    }
    return render(request, 'teacher/exam/exam_attempts.html', context)


def correct_exam(request, attempt_id):
    attempt = get_object_or_404(ExamAttempt, id=attempt_id)
    # Implement the logic to correct the exam here
    # ...
    context = {
        'attempt': attempt,
        # Add other context variables as needed
    }
    return render(request, 'teacher/exam/correct_exam.html', context)

@login_required
@role_required('student')
def exam_completed(request, attempt_id):
    attempt = get_object_or_404(ExamAttempt, id=attempt_id, student=request.user.userprofile)
    return render(request, 'student/exam/exam_completed.html', {'attempt': attempt})

def custom_403(request, exception):
    return render(request, 'errors/403.html', status=403)

def custom_404(request, exception):
    return render(request, 'errors/404.html', status=404)