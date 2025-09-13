# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import Count, Avg
from .models import *

# Кастомный админ для пользователей
@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = ['username', 'first_name', 'last_name', 'role', 'student_id', 'is_active']
    list_filter = ['role', 'is_active', 'date_joined']
    search_fields = ['username', 'first_name', 'last_name', 'student_id']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Дополнительная информация', {'fields': ('role', 'student_id')}),
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.role == 'student':
            return self.readonly_fields + ('student_id',)
        return self.readonly_fields

# Inline классы для связанных моделей
class CourseStudentInline(admin.TabularInline):
    model = CourseStudent
    extra = 1
    autocomplete_fields = ['student']

class SubjectInline(admin.TabularInline):
    model = Subject
    extra = 1
    show_change_link = True

class AnswerInline(admin.TabularInline):
    model = Answer
    extra = 2
    fields = ['text_md', 'is_correct']

class ExamSubjectInline(admin.TabularInline):
    model = ExamSubject
    extra = 1
    autocomplete_fields = ['subject']

# Основные админ-классы
@admin.register(Course)
class CourseAdmin(admin.ModelAdmin):
    list_display = ['name', 'description', 'student_count', 'exam_count', 'created_at']
    search_fields = ['name', 'description']
    inlines = [CourseStudentInline, SubjectInline]
    
    def student_count(self, obj):
        return obj.coursestudent_set.count()
    student_count.short_description = 'Студентов'
    
    def exam_count(self, obj):
        return obj.exams.count()
    exam_count.short_description = 'Экзаменов'

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'description', 'question_count']
    list_filter = ['course']
    search_fields = ['name', 'description']
    autocomplete_fields = ['course']
    
    def question_count(self, obj):
        return obj.questions.count()
    question_count.short_description = 'Вопросов'

@admin.register(Question)
class QuestionAdmin(admin.ModelAdmin):
    list_display = ['truncated_text', 'subject', 'difficulty', 'question_type', 'answer_count']
    list_filter = ['difficulty', 'question_type', 'subject__course']
    search_fields = ['text_md']
    autocomplete_fields = ['subject']
    inlines = [AnswerInline]
    
    def truncated_text(self, obj):
        return obj.text_md[:100] + ('...' if len(obj.text_md) > 100 else '')
    truncated_text.short_description = 'Текст вопроса'
    
    def answer_count(self, obj):
        return obj.answers.count()
    answer_count.short_description = 'Ответов'

@admin.register(Answer)
class AnswerAdmin(admin.ModelAdmin):
    list_display = ['truncated_text', 'question', 'is_correct']
    list_filter = ['is_correct', 'question__difficulty']
    search_fields = ['text_md']
    autocomplete_fields = ['question']
    
    def truncated_text(self, obj):
        return obj.text_md[:100] + ('...' if len(obj.text_md) > 100 else '')
    truncated_text.short_description = 'Текст ответа'

@admin.register(Exam)
class ExamAdmin(admin.ModelAdmin):
    list_display = ['name', 'course', 'open_time', 'close_time', 'duration_minutes', 
                   'attempts_allowed', 'participant_count', 'status_display']
    list_filter = ['course', 'open_time', 'close_time']
    search_fields = ['name', 'description']
    autocomplete_fields = ['course']
    inlines = [ExamSubjectInline]
    date_hierarchy = 'open_time'
    
    def participant_count(self, obj):
        return obj.results.values('student').distinct().count()
    participant_count.short_description = 'Участников'
    
    def status_display(self, obj):
        if obj.is_open():
            return format_html('<span style="color: green;">Открыт</span>')
        elif obj.is_upcoming():
            return format_html('<span style="color: orange;">Ожидается</span>')
        else:
            return format_html('<span style="color: red;">Закрыт</span>')
    status_display.short_description = 'Статус'

@admin.register(ExamSubject)
class ExamSubjectAdmin(admin.ModelAdmin):
    list_display = ['exam', 'subject', 'total_questions', 'max_score']
    list_filter = ['exam__course', 'subject']
    autocomplete_fields = ['exam', 'subject']

@admin.register(ExamResult)
class ExamResultAdmin(admin.ModelAdmin):
    list_filter = ['status', 'exam__course', 'start_time']
    search_fields = ['student__username', 'student__first_name', 'student__last_name', 'exam__name']
    autocomplete_fields = ['student', 'exam']
    readonly_fields = ('score', 'max_score', 'percentage_score')
    list_display = ('exam', 'student', 'attempt_number', 'score', 'max_score', 'percentage_score', 'status')

    date_hierarchy = 'start_time'
    
    def score_display(self, obj):
        return f"{obj.score}/{obj.max_score}"
    score_display.short_description = 'Баллы'
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('student', 'exam')

@admin.register(StudentAnswer)
class StudentAnswerAdmin(admin.ModelAdmin):
    list_display = ['exam_result', 'question_text', 'is_correct', 'points_earned', 'answered_at']
    list_filter = ['is_correct', 'exam_result__exam', 'question__difficulty']
    search_fields = ['exam_result__student__username', 'question__text_md']
    readonly_fields = ['answered_at']
    autocomplete_fields = ['exam_result', 'question']
    
    def question_text(self, obj):
        return obj.question.text_md[:100] + ('...' if len(obj.question.text_md) > 100 else '')
    question_text.short_description = 'Вопрос'

# Кастомные действия
@admin.action(description='Создать студенческие аккаунты')
def create_student_accounts(modeladmin, request, queryset):
    """Массовое создание студенческих аккаунтов"""
    # Эта функция будет реализована для массового импорта студентов
    pass

@admin.action(description='Экспорт результатов в Excel')
def export_results_to_excel(modeladmin, request, queryset):
    """Экспорт результатов экзаменов в Excel"""
    # Эта функция будет реализована для экспорта
    pass

# Настройка админ-панели
admin.site.site_header = "Система Онлайн-Экзаменов"
admin.site.site_title = "Админ-панель"
admin.site.index_title = "Управление системой экзаменов"

# Дополнительные настройки поиска
User.search_fields = ['username', 'first_name', 'last_name', 'student_id']
Course.search_fields = ['name']
Subject.search_fields = ['name']
Question.search_fields = ['text_md']