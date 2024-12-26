from django.shortcuts import render, redirect
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from .forms import UserRegistrationForm, LoginForm
from .models import Group, Specialty, UserProfile
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
    return render(request, 'teacher/courses/courses.html')

@login_required
def create_course(request):
    return render(request, 'teacher/courses/create_course.html')

@login_required
def student_dashboard(request):
    return render(request, 'student/dashboard.html')

@login_required
def student_courses(request):
    return render(request, 'student/courses.html')

@login_required
def create_exam(request):
    return render(request, 'teacher/exam/create_exam.html', {})

@login_required
def student_profile(request):
    return render(request, 'student/account/profile.html', {})

@login_required
def teacher_profile(request):
    return render(request, 'teacher/account/profile.html', {})