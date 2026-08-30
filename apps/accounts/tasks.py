from celery import shared_task
from django.contrib.auth import get_user_model
from django.core.mail import send_mail

User=get_user_model()

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
)
def send_welcome_email(user_id):
    user=User.objects.get(pk=user_id)
    send_mail(
        subject="Welcome to LedgerCore",
        message=(f"Hello {user.username},\n\n"
                "Welcome to LedgerCore."
    ),from_email=None,
    recipient_list=[user.email]
)