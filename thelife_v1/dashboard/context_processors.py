"""Context processor for sidebar navigation."""


def sidebar_context(request):
    """Provide sidebar navigation items to all templates."""
    if not request.user.is_authenticated:
        return {}

    sidebar_items = [
        {
            'label': 'Dashboard',
            'url': '/',
            'icon': 'layout-dashboard',
            'active_prefix': '/',
        },
        {
            'label': 'Activity Log',
            'url': '/activities/',
            'icon': 'clock',
            'active_prefix': '/activities/',
        },
        {
            'label': 'Work',
            'url': '/work/',
            'icon': 'briefcase',
            'active_prefix': '/work/',
        },
        {
            'label': 'Skills',
            'url': '/skills/',
            'icon': 'book-open',
            'active_prefix': '/skills/',
        },
        {
            'label': 'Entertainment',
            'url': '/entertainment/',
            'icon': 'clapperboard',
            'active_prefix': '/entertainment/',
        },
        {
            'label': 'Compute Mastery',
            'url': '/mastery/',
            'icon': 'terminal',
            'active_prefix': '/mastery/',
        },
        {
            'label': 'Scores',
            'url': '/scoring/',
            'icon': 'trophy',
            'active_prefix': '/scoring/',
        },
        {
            'label': 'Recurring Tasks',
            'url': '/activities/recurring/',
            'icon': 'repeat',
            'active_prefix': '/activities/recurring/',
        },
        {
            'label': 'Profile',
            'url': '/accounts/profile/',
            'icon': 'user',
            'active_prefix': '/accounts/profile/',
        },
    ]

    # Set active state
    path = request.path
    for item in sidebar_items:
        if item['active_prefix'] == '/':
            item['is_active'] = path == '/'
        else:
            item['is_active'] = path.startswith(item['active_prefix'])

    return {
        'sidebar_items': sidebar_items,
    }
