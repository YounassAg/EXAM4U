from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from .models import UserProfile, Group, Specialty, MCQChoice, Quiz, QuizQuestion, QuizChoice

class UserRegistrationForm(forms.ModelForm):
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)
    group = forms.ModelChoiceField(queryset=Group.objects.all(), required=False)
    specialty = forms.ModelChoiceField(queryset=Specialty.objects.all(), required=False)

    class Meta:
        model = User
        fields = ('username', 'first_name', 'last_name', 'email', 'group', 'specialty')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username=username).exists():
            raise ValidationError("A user with that username already exists.")
        return username

    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.email = self.cleaned_data['email']
        if commit:
            user.save()
            UserProfile.objects.create(
                user=user,
                first_name=self.cleaned_data['first_name'],
                last_name=self.cleaned_data['last_name'],
                role='student',  # Default role set to 'student'
                group=self.cleaned_data['group'],
                specialty=self.cleaned_data['specialty']
            )
        return user
    
        
class LoginForm(AuthenticationForm):
    username = forms.CharField(max_length=254, widget=forms.TextInput(attrs={'autofocus': True}))
    password = forms.CharField(label=("Password"), strip=False, widget=forms.PasswordInput)

class ExamForm(forms.Form):
    def __init__(self, *args, **kwargs):
        questions = kwargs.pop('questions')
        super(ExamForm, self).__init__(*args, **kwargs)

        for question in questions:
            choices = MCQChoice.objects.filter(question=question)
            if question.question_type == 'MCQ':
                if question.allow_multiple_answers:
                    self.fields[f'question_{question.id}'] = forms.MultipleChoiceField(
                        widget=forms.CheckboxSelectMultiple,
                        choices=[(choice.id, choice.choice_label) for choice in choices],
                        label=question.wording,
                        required=True,
                    )
                else:
                    self.fields[f'question_{question.id}'] = forms.ChoiceField(
                        widget=forms.RadioSelect,
                        choices=[(choice.id, choice.choice_label) for choice in choices],
                        label=question.wording,
                        required=True,
                    )
            else:
                self.fields[f'question_{question.id}'] = forms.CharField(
                    widget=forms.Textarea,
                    label=question.wording,
                    required=True,
                )

class QuizForm(forms.ModelForm):
    class Meta:
        model = Quiz
        fields = [
            'title', 'description', 'course', 'time_limit', 'passing_score', 
            'is_published', 'randomize_questions'
        ]
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-input'}),
            'description': forms.Textarea(attrs={'rows': 4, 'class': 'form-textarea'}),
            'course': forms.Select(attrs={'class': 'form-select'}),
            'time_limit': forms.NumberInput(attrs={'min': 1, 'max': 180, 'class': 'form-input'}),
            'passing_score': forms.NumberInput(attrs={'min': 0, 'max': 100, 'step': '0.1', 'class': 'form-input'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
            'randomize_questions': forms.CheckboxInput(attrs={'class': 'form-checkbox'}),
        }
        help_texts = {
            'title': 'Le titre du quiz',
            'description': 'Une description détaillée du quiz',
            'course': 'Le cours auquel ce quiz est associé',
            'time_limit': 'Durée en minutes (1-180)',
            'passing_score': 'Score minimum requis pour réussir (0-100)',
            'is_published': 'Rendre le quiz visible aux étudiants',
            'randomize_questions': 'Mélanger l\'ordre des questions pour chaque tentative',
        }

class QuizQuestionForm(forms.ModelForm):
    class Meta:
        model = QuizQuestion
        fields = ['question_text', 'points', 'explanation', 'is_required', 'allow_multiple_answers']
        widgets = {
            'question_text': forms.Textarea(attrs={'rows': 3}),
            'explanation': forms.Textarea(attrs={'rows': 2}),
            'points': forms.NumberInput(attrs={'min': 0.5, 'max': 100, 'step': '0.5'}),
        }
        help_texts = {
            'points': 'Points awarded for correct answer (0.5-100)',
            'explanation': 'Explanation shown after answering',
            'is_required': 'Question must be answered to submit the quiz',
            'allow_multiple_answers': 'Allow selecting multiple correct answers',
        }

class QuizChoiceForm(forms.ModelForm):
    class Meta:
        model = QuizChoice
        fields = ['choice_text', 'is_correct', 'explanation']
        widgets = {
            'choice_text': forms.TextInput(attrs={'class': 'w-full'}),
            'explanation': forms.Textarea(attrs={'rows': 2}),
        }
        
QuizChoiceFormSet = forms.inlineformset_factory(
    QuizQuestion,
    QuizChoice,
    form=QuizChoiceForm,
    extra=4,
    max_num=6,
    min_num=2,
    validate_min=True,
    can_delete=True
)