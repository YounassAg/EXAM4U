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

    def __str__(self):
        return f"{self.exam.title} - {self.student.user.first_name} {self.student.user.last_name} ({self.type})"



class Response(models.Model):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    response_text = models.TextField()
    response_grade = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Response to {self.question.wording[:30]}..."
    