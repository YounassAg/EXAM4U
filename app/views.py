from django.shortcuts import render, redirect, get_object_or_404
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
    return render(request, 'teacher/dashboard.html')

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

        # Process questions
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
                allow_multiple_answers=True
            )

            if question_type == 'MCQ':
                choice_count = int(request.POST.get(f'mcq_choice_count_{i}', 0))
                for j in range(1, choice_count + 1):
                    choice_label = request.POST.get(f'mcq_choice_{i}_{j}')
                    is_correct = request.POST.get(f'mcq_correct_{i}_{j}') == 'on'
                    MCQChoice.objects.create(
                        question=question,
                        choice_label=choice_label,
                        is_correct=is_correct
                    )

        messages.success(request, 'Exam created successfully!')
        return redirect('teacher_exam_list')

    else:
        courses = Course.objects.filter(teacher__user=request.user)
        groups = Group.objects.all()

        return render(request, 'teacher/exam/create_exam.html', {
            'courses': courses,
            'groups': groups
        })

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
@role_required('teacher')
def correction(request):
    return render(request, 'teacher/exam/correction.html')

@login_required
@role_required('teacher')
def exam_student_list(request):
    return render(request, 'teacher/exam/exam_student_list.html')

@login_required
@role_required('student')
def exam_completed(request, attempt_id):
    attempt = get_object_or_404(ExamAttempt, id=attempt_id, student=request.user.userprofile)
    return render(request, 'student/exam/exam_completed.html', {'attempt': attempt})

def custom_403(request, exception):
    return render(request, 'errors/403.html', status=403)

def custom_404(request, exception):
    return render(request, 'errors/404.html', status=404)