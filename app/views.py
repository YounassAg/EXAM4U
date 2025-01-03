from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction, IntegrityError
from django.core.exceptions import PermissionDenied
from django.contrib.auth import login, authenticate, logout
from django.contrib import messages
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from .forms import UserRegistrationForm, LoginForm, ExamForm
from .models import Course, Group, Exam, Question, MCQChoice, UserProfile, Specialty, ExamAttempt, Response
from django.http import JsonResponse, HttpResponse
from datetime import datetime
from reportlab.lib.colors import HexColor
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, Preformatted
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas
from io import BytesIO
import csv
import re


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
    return render(request, 'teacher/dashboard.html')


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
                existing_questions = set(exam.question_set.values_list('id', flat=True))
                processed_questions = set()
                question_count = int(request.POST.get('question_count', 0))
                for i in range(1, question_count + 1):
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
                        question = Question.objects.create(
                            exam=exam,
                            question_type=question_type,
                            wording=question_wording,
                            points=question_points,
                            allow_multiple_answers=(question_type == 'MCQ')
                        )
                        processed_questions.add(question.id)
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
@role_required('student')
def take_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    student = request.user.userprofile
    attempt = ExamAttempt.objects.filter(exam=exam, student=student, status='in_progress').first()
    if not attempt:
        completed_or_abandoned_attempts = ExamAttempt.objects.filter(
            exam=exam, student=student, status__in=['completed', 'abandoned']
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
def rattrapage_exam(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    students = UserProfile.objects.filter(group=exam.group, role='student')
    if request.method == 'POST':
        selected_students = request.POST.getlist('students')
        for student_id in selected_students:
            student = UserProfile.objects.get(id=student_id)
        ExamAttempt.objects.create(exam=exam, student=student)
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
def exam_attempts(request, exam_id):
    exam = get_object_or_404(Exam, id=exam_id)
    attempts = ExamAttempt.objects.filter(exam=exam, status='completed')
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
        if total_possible_points > 0:
            final_grade = total_points
        else:
            final_grade = 0
        attempt.grade = final_grade
        attempt.status = 'completed'
        attempt.save()
        messages.success(request, 'La correction a été enregistrée avec succès!')
        return redirect('exam_attempts', exam_id=attempt.exam.id)  
    responses_data = []
    for response in responses:
        responses_data.append({
            'response': response,
            'suggested_grade': None
        })
    context = {
        'attempt': attempt,
        'responses_data': responses_data,
    }
    return render(request, 'teacher/exam/correct_exam.html', context)


@login_required
@role_required('student')
def exam_completed(request, attempt_id):
    attempt = get_object_or_404(ExamAttempt, id=attempt_id, student=request.user.userprofile)
    return render(request, 'student/exam/exam_completed.html', {'attempt': attempt})


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
    
    if file_format == 'full':
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

    return HttpResponse(status=400, content="Invalid format.")


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
        # Draw footer line
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
        textColor=HexColor('#2e7d32'),  # Green color
        spaceAfter=6
    )
    incorrect_answer_style = ParagraphStyle(
        'IncorrectAnswerStyle',
        parent=styles['Normal'],
        fontSize=11,
        leftIndent=20,
        textColor=HexColor('#c62828'),  # Red color
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
    elements.append(Paragraph("Relevé de Notes", title_style))
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
            # Get all correct choices for this question
            correct_choices = MCQChoice.objects.filter(
                question=response.question,
                is_correct=True
            ).values_list('choice_label', flat=True)
            
            elements.append(Paragraph("Réponses choisies:", answer_style))
            
            # Split student answers using the exact separator
            if response.response_text:
                # Clean up the response text first
                cleaned_response = response.response_text.replace('~±■~■■~', ' ~±ſ~ƟƢ~ ')  # Handle malformed separator
                student_answers = [ans.strip() for ans in cleaned_response.split(' ~±ſ~ƟƢ~ ')]
                
                # Process each answer
                for answer in student_answers:
                    if not answer:
                        continue
                    
                    # Check if this specific answer matches any correct choice
                    is_correct = any(correct_choice.strip() == answer.strip() 
                                   for correct_choice in correct_choices)
                    
                    # Use the appropriate style based on correctness
                    style = correct_answer_style if is_correct else incorrect_answer_style
                    
                    # Add the answer with its color
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