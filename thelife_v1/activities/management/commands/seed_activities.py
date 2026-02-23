"""
Management command to seed activity categories and types.
Run: python manage.py seed_activities
"""
from django.core.management.base import BaseCommand
from activities.models import ActivityCategory, ActivityType


SEED_DATA = {
    'Work': {
        'icon': 'briefcase',
        'color': '#00BCD4',  # Cyan
        'sort_order': 1,
        'types': [
            'Coding / Development', 'Code Review', 'Meetings', 'Planning',
            'Documentation', 'Debugging', 'Research', 'Email & Communication',
            'Deployment', 'Design', 'Testing / QA', 'Mentoring',
            'Administrative', 'Training', 'Other Work',
        ],
    },
    'Skill Learning': {
        'icon': 'book-open',
        'color': '#10B981',  # Emerald
        'sort_order': 2,
        'types': [
            'Book Reading', 'Online Course (Coursera)', 'Online Course (Udemy)',
            'Online Course (YouTube)', 'Tutorial / Blog',
            'Practice / Hands-on', 'Certification Study', 'Workshop / Seminar',
            'Podcast / Audio Learning', 'Research Paper', 'Other Learning',
        ],
    },
    'Fitness': {
        'icon': 'dumbbell',
        'color': '#EF4444',  # Red
        'sort_order': 3,
        'types': [
            'Gym - Strength', 'Gym - Cardio', 'Running', 'Walking',
            'Yoga', 'Swimming', 'Cycling', 'Sports (Cricket, Football, etc.)',
            'Home Workout', 'Stretching', 'Martial Arts', 'Dance',
            'Hiking', 'Other Fitness',
        ],
    },
    'Entertainment': {
        'icon': 'clapperboard',
        'color': '#EC4899',  # Dark Pink
        'sort_order': 4,
        'types': [
            'Movie', 'Series / Short Film', 'Gaming',
            'Music Listening', 'Browsing / Social Media', 'Other Entertainment',
        ],
    },
    'Meals & Nutrition': {
        'icon': 'utensils',
        'color': '#F59E0B',  # Amber
        'sort_order': 5,
        'types': [
            'Breakfast', 'Lunch', 'Dinner', 'Snack',
            'Cooking / Meal Prep', 'Dining Out', 'Coffee / Tea Break',
        ],
    },
    'Social': {
        'icon': 'users',
        'color': '#8B5CF6',  # Purple
        'sort_order': 6,
        'types': [
            'Family Time', 'Friends Hangout', 'Date',
            'Networking / Professional', 'Phone / Video Call',
            'Community / Volunteering', 'Other Social',
        ],
    },
    'Self-Care & Rest': {
        'icon': 'heart',
        'color': '#06B6D4',  # Cyan lighter
        'sort_order': 7,
        'types': [
            'Meditation', 'Nap / Power Rest', 'Break / Relaxation',
            'Journaling', 'Therapy / Counseling', 'Mindfulness',
            'Sleep (Night)', 'Other Self-Care',
        ],
    },
    'Commute & Travel': {
        'icon': 'car',
        'color': '#64748B',  # Slate
        'sort_order': 8,
        'types': [
            'Drive', 'Public Transit', 'Walk', 'Bike / Ride',
            'Flight', 'Train (Long Distance)', 'Other Travel',
        ],
    },
    'Household': {
        'icon': 'home',
        'color': '#78716C',  # Stone
        'sort_order': 9,
        'types': [
            'Cleaning', 'Cooking', 'Laundry', 'Groceries',
            'Repairs / Maintenance', 'Organizing', 'Pet Care',
            'Gardening', 'Other Household',
        ],
    },
    'Finance': {
        'icon': 'wallet',
        'color': '#22C55E',  # Green
        'sort_order': 10,
        'types': [
            'Budgeting', 'Bills / Payments', 'Investment Review',
            'Tax Preparation', 'Financial Planning', 'Shopping',
            'Other Finance',
        ],
    },
    'Spirituality': {
        'icon': 'sunrise',
        'color': '#FBBF24',  # Yellow
        'sort_order': 11,
        'types': [
            'Prayer', 'Worship / Service', 'Reflection',
            'Religious Reading', 'Gratitude Practice', 'Other Spiritual',
        ],
    },
    'Personal Grooming': {
        'icon': 'sparkles',
        'color': '#F472B6',  # Pink
        'sort_order': 12,
        'types': [
            'Morning Routine', 'Skincare', 'Haircut / Salon',
            'Shopping (Personal)', 'Other Grooming',
        ],
    },
    'Creative': {
        'icon': 'palette',
        'color': '#A78BFA',  # Violet
        'sort_order': 13,
        'types': [
            'Writing', 'Music (Playing)', 'Art / Drawing',
            'Photography', 'Side Project', 'Content Creation',
            'Crafting / DIY', 'Other Creative',
        ],
    },
    'Errands & Appointments': {
        'icon': 'clipboard-list',
        'color': '#94A3B8',  # Gray-blue
        'sort_order': 14,
        'types': [
            'Medical / Doctor', 'Bank / Financial', 'Government / Legal',
            'Shopping (Errands)', 'Vehicle Service', 'Other Errands',
        ],
    },
    'General / Other': {
        'icon': 'circle',
        'color': '#6B7280',  # Gray
        'sort_order': 99,
        'types': [
            'Miscellaneous', 'Unplanned / Idle', 'Transition / Buffer',
        ],
    },
}


class Command(BaseCommand):
    help = 'Seed activity categories and types'

    def add_arguments(self, parser):
        parser.add_argument('--force', action='store_true',
                          help='Delete existing data and re-seed')

    def handle(self, *args, **options):
        if options['force']:
            ActivityType.objects.all().delete()
            ActivityCategory.objects.all().delete()
            self.stdout.write(self.style.WARNING('Cleared existing categories and types.'))

        created_cats = 0
        created_types = 0

        for cat_name, cat_data in SEED_DATA.items():
            cat, cat_created = ActivityCategory.objects.get_or_create(
                name=cat_name,
                defaults={
                    'icon': cat_data['icon'],
                    'color': cat_data['color'],
                    'sort_order': cat_data['sort_order'],
                },
            )
            if cat_created:
                created_cats += 1

            for type_name in cat_data['types']:
                _, type_created = ActivityType.objects.get_or_create(
                    category=cat, name=type_name,
                )
                if type_created:
                    created_types += 1

        self.stdout.write(self.style.SUCCESS(
            f'Seeded {created_cats} categories and {created_types} activity types.'))
