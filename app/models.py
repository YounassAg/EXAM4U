from django.db import models
from django.contrib.auth.models import User

class Specialty(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name


class Group(models.Model):
    group_code = models.CharField(max_length=50)
    specialty = models.ForeignKey(Specialty, on_delete=models.CASCADE)
    year = models.IntegerField()

    def __str__(self):
        return f"{self.group_code} ({self.year})"


class UserProfile(models.Model):
    ROLE_CHOICES = [
        ('administrator', 'Administrator'),
        ('teacher', 'Teacher'),
        ('student', 'Student'),
    ]

    user = models.OneToOneField(User, on_delete=models.CASCADE)
    last_name = models.CharField(max_length=100)
    first_name = models.CharField(max_length=100)
    role = models.CharField(max_length=13, choices=ROLE_CHOICES)
    group = models.ForeignKey(Group, on_delete=models.SET_NULL, null=True, blank=True)
    specialty = models.ForeignKey(Specialty, on_delete=models.SET_NULL, null=True, blank=True)
    creation_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.role})"


class Course(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    specialty = models.ForeignKey(Specialty, on_delete=models.CASCADE)
    teacher = models.ForeignKey(UserProfile, on_delete=models.CASCADE, limit_choices_to={'role': 'teacher'})

    def __str__(self):
        return self.title


class Exam(models.Model):
    title = models.CharField(max_length=255)
    description = models.TextField()
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    group = models.ForeignKey(Group, on_delete=models.CASCADE)
    duration = models.IntegerField()
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    max_attempts = models.IntegerField(default=1)

    def __str__(self):
        return self.title


class Question(models.Model):
    QUESTION_TYPE_CHOICES = [
        ('MCQ', 'Multiple Choice Question'),
        ('open', 'Open Question'),
        ('short_answer', 'Short Answer'),
    ]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    question_type = models.CharField(max_length=12, choices=QUESTION_TYPE_CHOICES)
    wording = models.TextField()
    points = models.FloatField(default=1.0)
    allow_multiple_answers = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.wording[:50]}..."  # Show only the first 50 characters of the question wording


class MCQChoice(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    choice_label = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)

    def __str__(self):
        return self.choice_label


class ExamAttempt(models.Model):
    EXAM_TYPE_CHOICES = [
        ('normal', 'Normal'),
        ('rattrapage', 'Rattrapage'),
    ]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=11,
        choices=[('in_progress', 'In Progress'), ('completed', 'Completed'), ('abandoned', 'Abandoned')],
        default='in_progress'
    )
    grade = models.FloatField(null=True, blank=True)
    type = models.CharField(
        max_length=15,
        choices=EXAM_TYPE_CHOICES,
        default='normal'
    )
    modified_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.exam.title} - {self.student.user.first_name} {self.student.user.last_name} ({self.type}) - {self.status}"



class Response(models.Model):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    response_text = models.TextField()
    response_grade = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Response to {self.question.wording[:30]}..."
    
class StudentActionLog(models.Model):
    ACTION_CHOICES = [
        ('page_load', 'Page Loaded'),
        ('page_unload', 'Page Unloaded'),
        ('tab_switch', 'Tab Switched'),
        ('navigation_attempt', 'Navigation Attempt'),
        ('question_answered', 'Question Answered'),
        ('inactivity_detected', 'Inactivity Detected'),
        ('copy_attempt', 'Copy Attempt'),
        ('screen_resize', 'Screen Resized'),
        ('network_disconnect', 'Network disconnect'),
        ('network_reconnect', 'Network reconnect'),
        ('suspicious_shortcut', 'Suspicious Shortcut Used'),
    ]

    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)  # Store additional context, e.g., the shortcut used

    def __str__(self):
        return f"{self.action} - {self.attempt.student} - {self.timestamp}"

class Quiz(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='quizzes')
    teacher = models.ForeignKey(UserProfile, on_delete=models.CASCADE, limit_choices_to={'role': 'teacher'})
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)
    time_limit = models.IntegerField(null=True, blank=True, help_text="Durée en minutes")
    passing_score = models.FloatField(default=50.0, help_text="Score minimum requis en pourcentage")
    randomize_questions = models.BooleanField(default=False, help_text="Mélanger l'ordre des questions pour chaque tentative")

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Quiz'
        verbose_name_plural = 'Quiz'

    def __str__(self):
        return self.title

    def get_total_points(self):
        return self.questions.aggregate(total=models.Sum('points'))['total'] or 0

    def get_student_best_score(self, student):
        attempts = self.attempts.filter(student=student, status='completed')
        if not attempts.exists():
            return None
        return attempts.aggregate(best_score=models.Max('score'))['best_score']

    def is_available_for_student(self, student):
        return self.is_published

class QuizQuestion(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='questions')
    question_text = models.TextField()
    points = models.IntegerField(default=1)
    explanation = models.TextField(blank=True, null=True, help_text="Explication affichée après la réponse")
    order = models.IntegerField(default=0)
    is_required = models.BooleanField(default=True, help_text="La question doit être répondue")
    allow_multiple_answers = models.BooleanField(default=False, help_text="Permettre la sélection de plusieurs réponses")

    class Meta:
        ordering = ['order']
        verbose_name = 'Question'
        verbose_name_plural = 'Questions'

    def __str__(self):
        return f"Question {self.order} - {self.quiz.title}"

    def get_correct_choices(self):
        return self.choices.filter(is_correct=True)

    def check_answer(self, selected_choices):
        correct_choices = set(self.get_correct_choices())
        selected_choices = set(selected_choices)
        
        if self.allow_multiple_answers:
            # For multiple answers, all correct choices must be selected and no incorrect ones
            if correct_choices == selected_choices:
                return self.points
            # Partial credit for partially correct answers
            correct_selected = len(correct_choices.intersection(selected_choices))
            incorrect_selected = len(selected_choices.difference(correct_choices))
            if correct_selected > 0 and incorrect_selected == 0:
                return (correct_selected / len(correct_choices)) * self.points
            return 0
        else:
            # For single answer, only one choice should be selected and it must be correct
            if len(selected_choices) == 1 and selected_choices.issubset(correct_choices):
                return self.points
            return 0

class QuizChoice(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name='choices')
    choice_text = models.CharField(max_length=255)
    is_correct = models.BooleanField(default=False)
    explanation = models.TextField(blank=True, null=True, help_text="Explication pour cette réponse")
    order = models.IntegerField(default=0)

    class Meta:
        ordering = ['order']
        verbose_name = 'Choix'
        verbose_name_plural = 'Choix'

    def __str__(self):
        return self.choice_text

class QuizAttempt(models.Model):
    quiz = models.ForeignKey(Quiz, on_delete=models.CASCADE, related_name='attempts')
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    start_time = models.DateTimeField(auto_now_add=True)
    end_time = models.DateTimeField(null=True, blank=True)
    score = models.FloatField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('in_progress', 'En cours'),
            ('completed', 'Terminé'),
            ('timed_out', 'Temps écoulé')
        ],
        default='in_progress'
    )
    time_spent = models.DurationField(null=True, blank=True)

    class Meta:
        ordering = ['-start_time']
        verbose_name = 'Tentative'
        verbose_name_plural = 'Tentatives'

    def __str__(self):
        return f"{self.quiz.title} - {self.student.user.get_full_name()} - {self.get_status_display()}"

    def calculate_score(self):
        total_points = self.quiz.get_total_points()
        earned_points = sum(response.calculate_points() for response in self.responses.all())
        self.score = (earned_points / total_points * 100) if total_points > 0 else 0
        return self.score

    def has_passed(self):
        return self.score >= self.quiz.passing_score if self.score is not None else False

class QuizResponse(models.Model):
    attempt = models.ForeignKey(QuizAttempt, on_delete=models.CASCADE, related_name='responses')
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE)
    selected_choices = models.ManyToManyField(QuizChoice)
    points_earned = models.FloatField(default=0)
    response_time = models.DurationField(null=True, blank=True)

    class Meta:
        verbose_name = 'Réponse'
        verbose_name_plural = 'Réponses'

    def __str__(self):
        return f"Réponse de {self.attempt.student.user.get_full_name()} - Question {self.question.order}"

    def calculate_points(self):
        self.points_earned = self.question.check_answer(self.selected_choices.all())
        self.save()
        return self.points_earned
