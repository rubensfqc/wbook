from datetime import datetime
from django.shortcuts import render
from django.utils.translation import gettext_lazy as _
from booking.models import PlatformSettings


def home_view(request):
    platform = PlatformSettings.get_solo()
    return render(request, 'website/home.html', {
        'company_name':  platform.platform_name or 'wbook365',
        'support_email': platform.support_email or 'support@wbook365.com',
        'tagline': _('Medical scheduling made simple — for doctors who care about their time.'),
        'year': datetime.now().year,
    })
