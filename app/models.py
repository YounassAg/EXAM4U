from django.db import models
from django.contrib.auth.models import User
from datetime import timedelta
from django.utils import timezone

class Specialty(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()

    def __str__(self):
        return self.name


class Group(models.Model):
    group_code = models.CharField(max_length=50)
    specialty = models.ForeignKey(Specialty, on_delete=models.CASCADE)
    start_year = models.IntegerField()
    end_year = models.IntegerField()

    def __str__(self):
        return f"{self.group_code} ({self.start_year}/{self.end_year})"


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
    is_taking_exam = models.BooleanField(default=False)  # New field to track if the student is taking an exam

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
    # max_attempts = models.IntegerField(default=1)

    def get_status(self):
        now = timezone.now()
        
        if now < self.start_date:
            return {
                'status': 'upcoming',
                'label': 'À venir',
                'color': 'bg-blue-500'
            }
        elif self.start_date <= now <= self.end_date:
            return {
                'status': 'in_progress',
                'label': 'En cours',
                'color': 'bg-yellow-500'
            }
        else:
            return {
                'status': 'completed',
                'label': 'Terminé',
                'color': 'bg-green-500'
            }
        
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

    STATUS_CHOICES = [
        ('in_progress', 'En cours'),
        ('completed', 'Terminé'),
        ('abandoned', 'Abandonné')
    ]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE)
    student = models.ForeignKey(UserProfile, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=11,
        choices=STATUS_CHOICES,
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
        return f"{self.exam.title} - {self.student.user.first_name} {self.student.user.last_name} ({self.type}) - {self.get_status_display()}"



class Response(models.Model):
    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE)
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    response_text = models.TextField()
    response_grade = models.FloatField(null=True, blank=True)

    def __str__(self):
        return f"Response to {self.question} by {self.attempt.student}"

    def calculate_mcq_score(self):
        """Calculate score for MCQ questions using the denial logic:
        - Each wrong answer denies one correct answer
        - If student selects some but not all correct answers, they get partial credit
        - Score is calculated as percentage of correct answers selected minus denials
        - Final score is rounded up to next 0.5 increment
        """
        if self.question.question_type != 'MCQ':
            return 0

        # Get all correct and selected choices
        correct_choices = set(self.question.mcqchoice_set.filter(is_correct=True).values_list('choice_label', flat=True))
        selected_choices = set(choice.strip() for choice in self.response_text.split(' ~±ſ~ƟƢ~ '))
        
        # Count correct and incorrect selections
        correct_selections = correct_choices.intersection(selected_choices)
        incorrect_selections = selected_choices.difference(correct_choices)
        
        # Calculate partial credit for correct selections
        partial_credit = len(correct_selections) / len(correct_choices)
        
        # Each incorrect selection denies one correct answer's worth of credit
        denial_penalty = len(incorrect_selections) / len(correct_choices)
        
        # Calculate final score percentage (partial credit minus denials)
        score_percentage = max(0, partial_credit - denial_penalty)
        
        # Calculate raw score based on question points
        raw_score = score_percentage * self.question.points
        
        # Round up to next 0.5 increment
        rounded_score = (int(raw_score * 2 + 0.99) / 2)
        return min(rounded_score, self.question.points)  # Ensure we don't exceed max points

class StudentActionLog(models.Model):
    ACTION_CHOICES = [
        ('Suspicious shortcut', 'Suspicious Shortcut Used'),
        ('Copy attempt', 'Copy Attempt'),
        ('Network disconnect', 'Network Disconnected'),
        ('Screen resize', 'Screen Resized'),
        ('Context menu', 'Context Menu Opened'),
        ('Dev tools', 'Developer Tools Opened'),
        ('Extended disconnect', 'Extended Network Disconnect'),
        ('Mouse leave', 'Mouse Left Window'),
        ('Focus lost', 'Window Focus Lost'),
        ('Text selection', 'Text Selection Attempted'),
        ('Network reconnect', 'Network Reconnected'),
        ('question_answered', 'Question Answered'),
        ('inactivity_detected', 'Inactivity Detected'),
        ('login_attempt', 'Login Attempt from Another Device'),  # New action type
    ]

    attempt = models.ForeignKey(ExamAttempt, on_delete=models.CASCADE)
    action = models.CharField(max_length=50, choices=ACTION_CHOICES)
    timestamp = models.DateTimeField(auto_now_add=True)
    details = models.TextField(blank=True, null=True)  # Store additional context, e.g., the shortcut used

    def __str__(self):
        return f"{self.action} - {self.attempt.student} - {self.timestamp}"


class ExamAttachment(models.Model):
    ATTACHMENT_TYPE_CHOICES = [
        ('image', 'Image'),
        ('video', 'Video'),
        ('document', 'Document'),
        ('other', 'Other'),
    ]

    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='attachments', null=True, blank=True)
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='attachments', null=True, blank=True)
    file = models.FileField(upload_to='exam_attachments/')
    file_type = models.CharField(max_length=10, choices=ATTACHMENT_TYPE_CHOICES)
    title = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title or self.file.name} ({self.get_file_type_display()})"

    def get_file_extension(self):
        return self.file.name.split('.')[-1].lower()

    def is_image(self):
        return self.file_type == 'image' or self.get_file_extension() in ['jpg', 'jpeg', 'png', 'gif', 'webp']

    def is_video(self):
        return self.file_type == 'video' or self.get_file_extension() in ['mp4', 'webm', 'ogg']

    def is_document(self):
        return self.file_type == 'document' or self.get_file_extension() in ['pdf', 'doc', 'docx', 'txt']
    
