from django import forms
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.core.exceptions import ValidationError
from .models import UserProfile, Group, Specialty, MCQChoice

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

