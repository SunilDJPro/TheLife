from django.contrib import admin
from .models import Problem, Tag, TestCase, Solution, JudgeResult


class TestCaseInline(admin.TabularInline):
    model = TestCase
    extra = 1


@admin.register(Tag)
class TagAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug']
    prepopulated_fields = {'slug': ('name',)}


@admin.register(Problem)
class ProblemAdmin(admin.ModelAdmin):
    list_display = ['title', 'difficulty', 'category', 'solution_count', 'created_at']
    list_filter = ['difficulty', 'category']
    search_fields = ['title']
    prepopulated_fields = {'slug': ('title',)}
    inlines = [TestCaseInline]


@admin.register(Solution)
class SolutionAdmin(admin.ModelAdmin):
    list_display = ['problem', 'language', 'version', 'is_accepted',
                    'median_runtime_us', 'created_at']
    list_filter = ['language', 'is_accepted']


@admin.register(JudgeResult)
class JudgeResultAdmin(admin.ModelAdmin):
    list_display = ['solution', 'test_case', 'status', 'median_time_us', 'ipc']
    list_filter = ['status']
