from django.shortcuts import render
from allauth.socialaccount.models import SocialToken
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from django.conf import settings

def index(request):
    events = []

    if request.user.is_authenticated:
        try:
            token = SocialToken.objects.get(account__user=request.user, account__provider='google')
            credentials = Credentials(
                token=token.token,
                refresh_token=token.token_secret,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=['https://www.googleapis.com/auth/calendar.readonly']
            )

            service = build('calendar', 'v3', credentials=credentials)
            result = service.events().list(
                calendarId='primary',
                maxResults=10,
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = result.get('items', [])
        except Exception as e:
            print("Error fetching calendar:", e)

    return render(request, 'home/index.html', {'events': events})
