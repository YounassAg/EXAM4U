from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from .forms import UserRegistrationForm, LoginForm
from .models import Course, Group, Exam, Question, MCQChoice, UserProfile, Specialty
from django.http import JsonResponse

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
        
    groups = Group.objects.all()  # All groups
    specialties = Specialty.objects.all()  # All specialties

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
def teacher_dashboard(request):
    return render(request, 'teacher/dashboard.html')


@login_required
def teacher_courses(request):
    teacher = request.user.userprofile
    courses = Course.objects.filter(teacher=teacher)
    return render(request, 'teacher/courses/courses.html', {'courses': courses})

@login_required
def student_courses(request):
    student_specialty = request.user.userprofile.specialty
    courses = Course.objects.filter(specialty=student_specialty)
    return render(request, 'student/courses/courses.html', {'courses': courses})

@login_required
def edit_course(request):
    return render(request, 'teacher/courses/edit_course.html')

@login_required
def delete_course(request):
    return render(request, 'teacher/courses/delete_course.html')

@login_required
def create_course(request):
    return render(request, 'teacher/courses/create_course.html')

@login_required
def student_dashboard(request):
    return render(request, 'student/dashboard.html')

@login_required
def create_exam(request):
    if request.method == 'POST':
        # Retrieve form data
        title = request.POST.get('title')
        description = request.POST.get('description')
        course_id = request.POST.get('course')
        group_id = request.POST.get('group')
        duration = request.POST.get('duration')
        max_attempts = request.POST.get('max_attempts')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')

        # Retrieve course and group objects
        course = Course.objects.get(id=course_id)
        group = Group.objects.get(id=group_id)

        # Create exam object
        exam = Exam.objects.create(
            title=title,
            description=description,
            course=course,
            group=group,
            duration=duration,
            max_attempts=max_attempts,
            start_date=start_date,
            end_date=end_date
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
                points=question_points
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

@login_required
def student_exam_list(request):
    student_group = request.user.userprofile.group
    exams = Exam.objects.filter(group=student_group)
    return render(request, 'student/exam/exam_list.html', {'exams': exams})

@login_required
def teacher_exam_list(request):
    # Get the teacher's UserProfile (for current user)
    teacher_profile = request.user.userprofile
    
    # Filter exams where the logged-in teacher is the creator of the course
    exams = Exam.objects.filter(course__teacher=teacher_profile)
    
    return render(request, 'teacher/exam/exam_list.html', {'exams': exams})

@login_required
def student_profile(request):
    return render(request, 'student/account/profile.html', {})

@login_required
def teacher_profile(request):
    return render(request, 'teacher/account/profile.html', {})