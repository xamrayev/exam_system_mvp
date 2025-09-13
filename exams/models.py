# models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
from datetime import timedelta

class User(AbstractUser):
    ROLE_CHOICES = [
        ('student', 'Студент'),
        ('admin', 'Администратор'),
    ]
    
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default='student')
    student_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    
    def save(self, *args, **kwargs):
        if not self.student_id and self.role == 'student':
            self.student_id = str(uuid.uuid4())[:8].upper()
        super().save(*args, **kwargs)

class Course(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название курса")
    description = models.TextField(blank=True, verbose_name="Описание")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Курс"
        verbose_name_plural = "Курсы"
    
    def __str__(self):
        return self.name

class CourseStudent(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE)
    student = models.ForeignKey(User, on_delete=models.CASCADE, limit_choices_to={'role': 'student'})
    enrolled_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['course', 'student']
        verbose_name = "Студент курса"
        verbose_name_plural = "Студенты курсов"

class Subject(models.Model):
    name = models.CharField(max_length=200, verbose_name="Название предмета")
    description = models.TextField(blank=True, verbose_name="Описание")
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='subjects')
    
    class Meta:
        verbose_name = "Предмет"
        verbose_name_plural = "Предметы"
    
    def __str__(self):
        return f"{self.course.name} - {self.name}"

class Question(models.Model):
    DIFFICULTY_CHOICES = [
        ('easy', 'Легкий'),
        ('medium', 'Средний'),
        ('hard', 'Сложный'),
    ]
    
    TYPE_CHOICES = [
        ('single', 'Один правильный ответ'),
        ('multiple', 'Несколько правильных ответов'),
        ('open', 'Открытый ответ'),
    ]
    
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE, related_name='questions')
    text_md = models.TextField(verbose_name="Текст вопроса (Markdown)")
    difficulty = models.CharField(max_length=10, choices=DIFFICULTY_CHOICES, default='medium')
    question_type = models.CharField(max_length=10, choices=TYPE_CHOICES, default='single')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Вопрос"
        verbose_name_plural = "Вопросы"
    
    def __str__(self):
        return f"{self.subject.name} - {self.text_md[:50]}..."

class Answer(models.Model):
    question = models.ForeignKey(Question, on_delete=models.CASCADE, related_name='answers')
    text_md = models.TextField(verbose_name="Текст ответа (Markdown)")
    is_correct = models.BooleanField(default=False, verbose_name="Правильный ответ")
    
    class Meta:
        verbose_name = "Вариант ответа"
        verbose_name_plural = "Варианты ответов"
    
    def __str__(self):
        return f"{self.question.text_md[:30]}... - {self.text_md[:30]}..."

class Exam(models.Model):
    course = models.ForeignKey(Course, on_delete=models.CASCADE, related_name='exams')
    name = models.CharField(max_length=200, verbose_name="Название экзамена")
    description = models.TextField(blank=True, verbose_name="Описание")
    open_time = models.DateTimeField(verbose_name="Время открытия")
    close_time = models.DateTimeField(verbose_name="Время закрытия")
    duration_minutes = models.IntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(300)],
        verbose_name="Продолжительность (минуты)"
    )
    attempts_allowed = models.IntegerField(
        default=1, validators=[MinValueValidator(1), MaxValueValidator(5)],
        verbose_name="Количество попыток"
    )
    
    class Meta:
        verbose_name = "Экзамен"
        verbose_name_plural = "Экзамены"
    
    def __str__(self):
        return f"{self.course.name} - {self.name}"
    
    def is_open(self):
        now = timezone.now()
        return self.open_time <= now <= self.close_time
    
    def is_upcoming(self):
        return timezone.now() < self.open_time
    
    @property
    def duration(self):
        """Возвращает продолжительность экзамена как timedelta"""
        return timedelta(minutes=self.duration_minutes)

class ExamSubject(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name='exam_subjects')
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    
    # Количество вопросов по сложности
    easy_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    medium_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    hard_count = models.IntegerField(default=0, validators=[MinValueValidator(0)])
    
    # Баллы за вопросы по сложности
    easy_points = models.IntegerField(default=1, validators=[MinValueValidator(0)])
    medium_points = models.IntegerField(default=2, validators=[MinValueValidator(0)])
    hard_points = models.IntegerField(default=3, validators=[MinValueValidator(0)])
    
    class Meta:
        unique_together = ['exam', 'subject']
        verbose_name = "Предмет экзамена"
        verbose_name_plural = "Предметы экзамена"
    
    def total_questions(self):
        return self.easy_count + self.medium_count + self.hard_count
    
    def max_score(self):
        return (self.easy_count * self.easy_points + 
                self.medium_count * self.medium_points + 
                self.hard_count * self.hard_points)

class ExamResult(models.Model):
    exam = models.ForeignKey(Exam, on_delete=models.CASCADE, related_name="results")
    student = models.ForeignKey(User, on_delete=models.CASCADE, related_name="exam_results")
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=[("in_progress", "В процессе"), ("finished", "Завершен"), ("time_expired", "Время вышло")],
        default="in_progress"
    )
    score = models.FloatField(default=0)
    max_score = models.FloatField(default=0)
    questions = models.ManyToManyField("Question", related_name="exam_results", blank=True)

    def __str__(self):
        return f"{self.student} - {self.exam} ({self.status})"

    def percentage_score(self):
        """Процент набранных баллов"""
        if self.max_score > 0:
            return round((self.score / self.max_score) * 100, 2)
        return 0
    percentage_score.short_description = "Результат %"

    def attempt_number(self):
        """Номер попытки для этого студента по экзамену"""
        return ExamResult.objects.filter(exam=self.exam, student=self.student, id__lte=self.id).count()
    attempt_number.short_description = "Попытка №"

    def is_expired(self):
        if self.start_time and self.exam.duration_minutes:
            elapsed = timezone.now() - self.start_time
            return elapsed.total_seconds() > (self.exam.duration_minutes * 60)
        return False

    def time_remaining(self):
        if not self.start_time:
            return None
        elapsed = timezone.now() - self.start_time
        return max(self.exam.duration - elapsed, timedelta(0))


class StudentAnswer(models.Model):
    exam_result = models.ForeignKey(ExamResult, on_delete=models.CASCADE, related_name='student_answers')
    question = models.ForeignKey(Question, on_delete=models.CASCADE)
    selected_answers = models.ManyToManyField(Answer, blank=True)  # For single/multiple choice
    answer_text = models.TextField(blank=True)  # For open questions
    is_correct = models.BooleanField(default=False)
    points_earned = models.IntegerField(default=0)
    answered_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['exam_result', 'question']
        verbose_name = "Ответ студента"
        verbose_name_plural = "Ответы студентов"
    
    def __str__(self):
        return f"{self.exam_result.student.username} - {self.question.text_md[:30]}..."