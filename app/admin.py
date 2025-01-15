from django.contrib import admin
from .models import Specialty, ExamAttempt, UserProfile, Group, Course, Exam, Question, MCQChoice, Response, StudentActionLog, Quiz, QuizQuestion, QuizChoice, QuizAttempt, QuizResponse

admin.site.register(Specialty)
admin.site.register(UserProfile)
admin.site.register(Group)
admin.site.register(Course)
admin.site.register(Exam)
admin.site.register(ExamAttempt)
admin.site.register(Question)
admin.site.register(MCQChoice)
admin.site.register(Response)
admin.site.register(StudentActionLog)
admin.site.register(Quiz)
admin.site.register(QuizQuestion)
admin.site.register(QuizChoice)
admin.site.register(QuizAttempt)
admin.site.register(QuizResponse)