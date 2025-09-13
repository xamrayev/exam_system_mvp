import json
import random
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils import timezone
from django.contrib import messages
from django.db import transaction
from django.db.models import Sum
from .models import *

# ----------------------
# Аутентификация
# ----------------------
def student_login(request):
    """Вход студента по student_id"""
    if request.method == 'POST':
        student_id = request.POST.get('student_id', '').strip().upper()
        try:
            user = User.objects.get(student_id=student_id, role='student')
            login(request, user)
            return redirect('exam_list')
        except User.DoesNotExist:
            messages.error(request, 'Неверный ID студента')
    return render(request, 'exams/student_login.html')

@login_required
def logout_view(request):
    """Выход из системы"""
    logout(request)
    return redirect('student_login')

# ----------------------
# Экзамены
# ----------------------
@login_required
def exam_list(request):
    """Список доступных экзаменов"""
    if request.user.role != 'student':
        return redirect('admin:index')

    now = timezone.now()
    student_courses = CourseStudent.objects.filter(student=request.user).values_list('course_id', flat=True)

    exams = Exam.objects.filter(
        course_id__in=student_courses,
        open_time__lte=now,
        close_time__gte=now
    ).order_by('close_time')

    exam_data = []
    for exam in exams:
        attempts = ExamResult.objects.filter(exam=exam, student=request.user).count()
        can_take = exam.attempts_allowed is None or attempts < exam.attempts_allowed
        in_progress = ExamResult.objects.filter(exam=exam, student=request.user, status='in_progress').first()
        exam_data.append({
            'exam': exam,
            'attempts_made': attempts,
            'can_take': can_take,
            'in_progress': in_progress,
        })

    return render(request, 'exams/exam_list.html', {'exam_data': exam_data})

@login_required
def start_exam(request, exam_id):
    """Начало экзамена"""
    exam = get_object_or_404(Exam, pk=exam_id)
    student = request.user

    attempts = ExamResult.objects.filter(exam=exam, student=student).count()
    can_take = exam.attempts_allowed is None or attempts < exam.attempts_allowed
    if not can_take:
        return render(request, 'exams/no_attempts.html', {"exam": exam})

    exam_result = ExamResult.objects.create(
        exam=exam,
        student=student,
        start_time=timezone.now(),
        status="in_progress"
    )

    # ИСПРАВЛЕНИЕ: правильная генерация вопросов
    selected_questions = []
    for exam_subject in exam.exam_subjects.all():
        selected_questions.extend(get_random_questions(exam_subject, exam_subject.subject))

    exam_result.questions.set(selected_questions)
    
    # ДОБАВИТЬ: создание записей StudentAnswer для каждого вопроса
    for question in selected_questions:
        StudentAnswer.objects.create(
            exam_result=exam_result,
            question=question
        )
    
    return redirect('take_exam', exam_result_id=exam_result.id)

@login_required
def take_exam(request, exam_result_id):
    exam_result = get_object_or_404(ExamResult, pk=exam_result_id, student=request.user)
    
    if exam_result.is_expired():
        return finalize_exam(exam_result, "time_expired")
    
    # ОТЛАДКА: проверим данные
    student_answers = exam_result.student_answers.select_related(
        'question', 
        'question__subject'
    ).prefetch_related(
        'question__answers',
        'selected_answers'
    )
    
    # Отладочная информация
    print(f"ExamResult ID: {exam_result.id}")
    print(f"Student answers count: {student_answers.count()}")
    
    # for sa in student_answers:
    #     print(f"Question {sa.question.id}: type={sa.question.question_type}, answers_count={sa.question.answers.count()}")
    #     for answer in sa.question.answers.all():
    #         # print(f"  Answer {answer.id}: {answer.text[:50]}...")
    
    return render(request, 'exams/take_exam.html', {
        'exam_result': exam_result,
        'student_answers': student_answers,
        'time_remaining': exam_result.time_remaining()
    })


# ----------------------
# Ответы
# ----------------------
@login_required
@require_POST
@csrf_exempt
def save_answer(request, exam_result_id):  # ИСПРАВИТЬ: добавить exam_result_id в параметры
    try:
        data = json.loads(request.body)
        student_answer_id = data.get('student_answer_id')
        answer_ids = data.get('answer_ids', [])
        answer_text = data.get('answer_text', '')

        student_answer = get_object_or_404(
            StudentAnswer,
            id=student_answer_id,
            exam_result__student=request.user,
            exam_result__status='in_progress'
        )
        
        if student_answer.exam_result.is_expired():
            return JsonResponse({'success': False, 'error': 'Время истекло'})

        with transaction.atomic():
            if student_answer.question.question_type == 'open':
                student_answer.answer_text = answer_text
                student_answer.is_correct = None
                student_answer.points_earned = None
            else:
                student_answer.selected_answers.clear()
                if answer_ids:
                    answers = Answer.objects.filter(id__in=answer_ids, question=student_answer.question)
                    student_answer.selected_answers.set(answers)
                check_answer_correctness(student_answer)
            student_answer.save()

        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def check_answer_correctness(student_answer):
    """Проверка ответа"""
    question = student_answer.question
    correct_answers = set(question.answers.filter(is_correct=True).values_list('id', flat=True))
    selected_answers = set(student_answer.selected_answers.values_list('id', flat=True))
    student_answer.is_correct = (correct_answers == selected_answers and len(selected_answers) > 0)
    if student_answer.is_correct:
        exam_subject = ExamSubject.objects.filter(exam=student_answer.exam_result.exam, subject=question.subject).first()
        if exam_subject:
            if question.difficulty == 'easy':
                student_answer.points_earned = exam_subject.easy_points
            elif question.difficulty == 'medium':
                student_answer.points_earned = exam_subject.medium_points
            else:
                student_answer.points_earned = exam_subject.hard_points
    else:
        student_answer.points_earned = 0

# ----------------------
# Завершение экзамена
# ----------------------
@require_POST
@login_required  
def finish_exam(request, exam_result_id):
    try:
        data = json.loads(request.body)
        exam_result_id = data.get('exam_result_id')
        exam_result = get_object_or_404(ExamResult, pk=exam_result_id, student=request.user)
        finalize_exam(exam_result, "finished")
        return JsonResponse({'success': True})
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

def finalize_exam(exam_result, status):
    """Финализирует экзамен"""
    with transaction.atomic():
        exam_result.end_time = timezone.now()
        exam_result.status = status
        exam_result.score = exam_result.student_answers.aggregate(total=Sum('points_earned'))['total'] or 0
        
        # ДОБАВИТЬ: расчет максимального балла
        max_score = 0
        for exam_subject in exam_result.exam.exam_subjects.all():
            max_score += exam_subject.max_score()
        exam_result.max_score = max_score
        
        exam_result.save()
    return redirect('exam_result_detail', exam_result_id=exam_result.id)

# ----------------------
# Результаты
# ----------------------
@login_required
def exam_results_list(request):
    """Все экзамены студента"""
    results = ExamResult.objects.filter(student=request.user).order_by('-start_time')
    return render(request, 'exams/exam_results_list.html', {"results": results})

@login_required
def exam_result_detail(request, exam_result_id):
    """Детальный результат экзамена"""
    exam_result = get_object_or_404(ExamResult, id=exam_result_id, student=request.user)
    if exam_result.status == 'in_progress':
        return redirect('take_exam', exam_result_id=exam_result.id)

    student_answers = exam_result.student_answers.select_related('question').prefetch_related('question__answers', 'selected_answers')
    subject_stats = {}
    for answer in student_answers:
        subject = answer.question.subject.name if answer.question.subject else "Без предмета"
        if subject not in subject_stats:
            subject_stats[subject] = {'correct': 0, 'total': 0, 'points': 0}
        subject_stats[subject]['total'] += 1
        if answer.is_correct:
            subject_stats[subject]['correct'] += 1
        subject_stats[subject]['points'] += answer.points_earned or 0

    return render(request, 'exams/exam_result_detail.html', {
        'exam_result': exam_result,
        'student_answers': student_answers,
        'subject_stats': subject_stats,
    })

# ----------------------
# Утилиты
# ----------------------

def get_random_questions(exam_subject, subject):
    """Случайные вопросы"""
    def random_subset(queryset, count):
        ids = list(queryset.values_list('id', flat=True))
        if not ids:
            return []
        return list(Question.objects.filter(id__in=random.sample(ids, min(len(ids), count))))

    # ИСПРАВЛЕНИЕ: использовать exam_subject.subject вместо subject
    easy = random_subset(Question.objects.filter(subject=exam_subject.subject, difficulty='easy'), exam_subject.easy_count)
    medium = random_subset(Question.objects.filter(subject=exam_subject.subject, difficulty='medium'), exam_subject.medium_count)
    hard = random_subset(Question.objects.filter(subject=exam_subject.subject, difficulty='hard'), exam_subject.hard_count)

    return easy + medium + hard

@login_required
def exam_results(request):
    student = request.user
    results = ExamResult.objects.filter(student=student)

    stats = []
    for result in results:
        answers = StudentAnswer.objects.filter(exam_result=result)
        subject_stats = {}

        for answer in answers:
            subject = answer.question.subject.name if answer.question.subject else "Без предмета"
            if subject not in subject_stats:
                subject_stats[subject] = {"correct": 0, "total": 0}
            if answer.is_correct:
                subject_stats[subject]["correct"] += 1
            subject_stats[subject]["total"] += 1

        stats.append({"exam": result.exam, "subject_stats": subject_stats})

    return render(request, 'exam/results.html', {"stats": stats})

