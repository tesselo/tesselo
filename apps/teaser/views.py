from django.core.mail import BadHeaderError, send_mail
from django.http import JsonResponse
from teaser.forms import ContactForm

MSG_TEMPLATE = '''A message has been submitted to the Tesselo contact form

----------------------------------

From: {name}

----------------------------------

Email: {from_email}

----------------------------------

Message:

{message}


---
Sent to you by the Tesselo bots.
'''


def teasercontact(request):
    data = {}
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            from_email = form.cleaned_data['email']
            message_text = form.cleaned_data['message']
            message = MSG_TEMPLATE.format(
                name=name,
                from_email=from_email,
                message=message_text,
            )
            try:
                send_mail('Teaser contact by {}'.format(name), message, from_email, ['teaser@tesselo.com'])
            except BadHeaderError:
                return JsonResponse('Invalid header found.')

            data['success'] = True
            data['confirmation'] = 'Congratulations. Your message has been sent successfully'
        else:
            errors = {}
            if 'name' in form.errors:
                errors['name'] = 'Name is required.'
            if 'email' in form.errors:
                errors['email'] = 'Email is invalid.'
            if 'message' in form.errors:
                errors['message'] = 'Message is required.'

            data['success'] = False
            data['errors'] = errors

    return JsonResponse(data)
