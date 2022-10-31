from django.core import mail


def send_mass_html_mail(datatuple):
    connection = mail.get_connection(fail_silently=False)
    messages = []
    for subject, text, html, from_email, recipient in datatuple:
        message = mail.EmailMultiAlternatives(subject, text, from_email, recipient)
        message.attach_alternative(html, 'text/html')
        messages.append(message)

    return connection.send_messages(messages)
