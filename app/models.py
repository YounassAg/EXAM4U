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

    def get_statistics(self):
        attempts = self.attempts.all()
        total_attempts = attempts.count()
        
        if total_attempts == 0:
            return {
                'total_attempts': 0,
                'avg_score': 0,
                'completion_rate': 0,
                'pass_rate': 0,
                'avg_time': None,
                'question_stats': []
            }

        completed_attempts = attempts.filter(status='completed')
        passed_attempts = completed_attempts.filter(score__gte=self.passing_score)

        # Calculate average time spent
        completed_with_time = completed_attempts.exclude(time_spent=None)
        avg_time = completed_with_time.aggregate(avg_time=models.Avg('time_spent'))['avg_time'] if completed_with_time.exists() else None

        # Question statistics
        question_stats = []
        for question in self.questions.all():
            responses = QuizResponse.objects.filter(attempt__quiz=self, question=question)
            total_responses = responses.count()
            if total_responses > 0:
                correct_responses = responses.filter(points_earned=question.points).count()
                question_stats.append({
                    'question_id': question.id,
                    'question_text': question.question_text,
                    'total_responses': total_responses,
                    'correct_responses': correct_responses,
                    'success_rate': (correct_responses / total_responses) * 100,
                    'avg_points': responses.aggregate(avg_points=models.Avg('points_earned'))['avg_points'] or 0
                })

        return {
            'total_attempts': total_attempts,
            'avg_score': attempts.aggregate(avg_score=models.Avg('score'))['avg_score'] or 0,
            'completion_rate': (completed_attempts.count() / total_attempts) * 100 if total_attempts > 0 else 0,
            'pass_rate': (passed_attempts.count() / completed_attempts.count()) * 100 if completed_attempts.exists() else 0,
            'avg_time': avg_time,
            'question_stats': question_stats
        }

    def get_student_statistics(self, student):
        student_attempts = self.attempts.filter(student=student)
        total_attempts = student_attempts.count()
        
        if total_attempts == 0:
            return None

        best_attempt = student_attempts.filter(score__isnull=False).order_by('-score').first()
        last_attempt = student_attempts.order_by('-start_time').first()
        completed_attempts = student_attempts.filter(score__isnull=False)
        
        return {
            'total_attempts': total_attempts,
            'best_score': best_attempt.score if best_attempt else 0,
            'last_score': last_attempt.score if last_attempt and last_attempt.score is not None else 0,
            'average_score': completed_attempts.aggregate(avg_score=models.Avg('score'))['avg_score'] or 0,
            'has_passed': completed_attempts.filter(score__gte=self.passing_score).exists(),
            'last_attempt_date': last_attempt.start_time if last_attempt else None
        }

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
        verbose_name = 'Question_Quiz'
        verbose_name_plural = 'Questions Quiz'

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

    def validate_submission_time(self):
        if not self.quiz.time_limit:
            return True
            
        if not self.start_time or not self.end_time:
            return False
            
        actual_duration = self.end_time - self.start_time
        allowed_duration = timedelta(minutes=self.quiz.time_limit)
        
        # Add a small buffer (30 seconds) for network latency
        buffer_time = timedelta(seconds=30)
        return actual_duration <= (allowed_duration + buffer_time)

    def is_time_expired(self):
        if not self.quiz.time_limit or not self.start_time:
            return False
            
        time_limit = timedelta(minutes=self.quiz.time_limit)
        return timezone.now() > (self.start_time + time_limit)

    def get_remaining_time(self):
        if not self.quiz.time_limit or not self.start_time:
            return None
            
        time_limit = timedelta(minutes=self.quiz.time_limit)
        remaining = (self.start_time + time_limit) - timezone.now()
        return max(remaining, timedelta(0))

    def update_time_spent(self):
        if self.start_time and self.end_time:
            self.time_spent = self.end_time - self.start_time
            self.save(update_fields=['time_spent'])

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

class QuestionBank(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    teacher = models.ForeignKey(UserProfile, on_delete=models.CASCADE, limit_choices_to={'role': 'teacher'})
    questions = models.ManyToManyField(QuizQuestion, related_name='banks')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Banque de questions'
        verbose_name_plural = 'Banques de questions'

    def __str__(self):
        return f"{self.name} ({self.questions.count()} questions)"

    def add_question(self, question):
        if question.quiz.teacher == self.teacher:
            self.questions.add(question)
            return True
        return False

    def remove_question(self, question):
        self.questions.remove(question)

    def get_questions_by_type(self, question_type=None):
        if question_type:
            return self.questions.filter(question_type=question_type)
        return self.questions.all()
