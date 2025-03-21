from django.shortcuts import render
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from django.conf import settings
from allauth.socialaccount.models import SocialToken, SocialAccount

from django.shortcuts import render
from allauth.socialaccount.models import SocialToken, SocialAccount
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from django.conf import settings

def index(request):
    events = []
    all_calendars = []

    if request.user.is_authenticated:
        # ✅ Debugging: Print if user is connected to Google
        print("User is:", request.user.email)
        print("Accounts:", SocialAccount.objects.filter(user=request.user))
        print("Tokens:", SocialToken.objects.filter(account__user=request.user))

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
            calendar_list = service.calendarList().list().execute()

            for calendar_entry in calendar_list.get('items', []):
                calendar_id = calendar_entry['id']
                all_calendars.append({
                    'id': calendar_id,
                    'name': calendar_entry['summary'],
                    'color': calendar_entry.get('backgroundColor', '#3788d8')
                })

                result = service.events().list(
                    calendarId=calendar_id,
                    maxResults=10,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()

                for event in result.get('items', []):
                    events.append({
                        'summary': event.get('summary', 'No Title'),
                        'start': event.get('start', {}).get('dateTime') or event.get('start', {}).get('date'),
                        'end': event.get('end', {}).get('dateTime') or event.get('end', {}).get('date'),
                        'backgroundColor': calendar_entry.get('backgroundColor', '#3788d8'),
                        'calendarId': calendar_id
                    })

        except Exception as e:
            print("❌ Error fetching calendar data:", e)
            print("Session keys:", request.session.keys())


    return render(request, 'home/index.html', {
        'events': events,
        'calendars': all_calendars
    })
