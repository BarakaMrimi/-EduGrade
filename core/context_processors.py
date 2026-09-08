from core.access import unread_notification_count


def notifications(request):
    return {
        'unread_notification_count': unread_notification_count(request.user)
    }
