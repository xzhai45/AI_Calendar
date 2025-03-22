from django.shortcuts import render
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from django.conf import settings
from allauth.socialaccount.models import SocialToken, SocialAccount
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
from django.utils.timezone import localtime

def add_event_to_google(request):
    if request.method == "POST":
        if not request.user.is_authenticated:
            return JsonResponse({"error": "User not authenticated"}, status=403)

        try:
            token = SocialToken.objects.get(account__user=request.user, account__provider='google')
        except SocialToken.DoesNotExist:
            return JsonResponse({"error": "Google token not found for user"}, status=404)

        credentials = Credentials(
            token=token.token,
            refresh_token=token.token_secret,
            token_uri='https://oauth2.googleapis.com/token',
            client_id=settings.GOOGLE_CLIENT_ID,
            client_secret=settings.GOOGLE_CLIENT_SECRET,
            scopes=['https://www.googleapis.com/auth/calendar']
        )

        service = build('calendar', 'v3', credentials=credentials)

        event_data = request.POST

        # Required fields
        start = event_data.get("start")
        end = event_data.get("end")
        title = event_data.get("title")

        if not (start and end and title):
            return JsonResponse({"error": "Missing required fields (title, start, or end)"}, status=400)

        # Base event
        event = {
            'summary': title,
            'start': {
                'dateTime': start,
                'timeZone': 'America/New_York',
            },
            'end': {
                'dateTime': end,
                'timeZone': 'America/New_York',
            },
        }

        # Optional fields
        location = event_data.get("location")
        description = event_data.get("description")

        if location:
            event["location"] = location
        if description:
            event["description"] = description

        # Optional: Recurrence
        recurrence = event_data.get("recurrence")  # Should be something like 'RRULE:FREQ=DAILY;COUNT=2'
        if recurrence:
            event["recurrence"] = [recurrence]

        # Optional: Attendees (comma-separated emails)
        attendees_raw = event_data.get("attendees")  # e.g., "a@example.com, b@example.com"
        if attendees_raw:
            attendee_list = [{'email': email.strip()} for email in attendees_raw.split(",") if email.strip()]
            if attendee_list:
                event["attendees"] = attendee_list

        # Optional: Reminders (useDefault=False + custom times if needed)
        if event_data.get("use_custom_reminders") == "true":
            event["reminders"] = {
                'useDefault': False,
                'overrides': [
                    {'method': 'email', 'minutes': 24 * 60},
                    {'method': 'popup', 'minutes': 10},
                ]
            }

        try:
            print("🚨 Event being sent to Google Calendar:", json.dumps(event, indent=2))
            created_event = service.events().insert(calendarId='primary', body=event).execute()
            print("✅ Event created:", created_event.get('htmlLink'))
        except Exception as e:
            print("❌ Failed to create event:", e)
            return JsonResponse({"error": str(e)}, status=500)

        return JsonResponse({
            "message": "Event added to Google Calendar",
            "eventId": created_event["id"],
            "link": created_event.get("htmlLink")
        })

    return JsonResponse({"error": "Invalid request method"}, status=400)

def delete_event_from_google(request):
    if request.method == "POST":
        if not request.user.is_authenticated:
            return JsonResponse({"error": "User not authenticated"}, status=403)

        try:
            body = json.loads(request.body)
            event_id = body.get("eventId")
            calendar_id = body.get("calendarId", "primary")

            if not event_id:
                return JsonResponse({"error": "Missing event ID"}, status=400)

            token = SocialToken.objects.get(account__user=request.user, account__provider='google')
            credentials = Credentials(
                token=token.token,
                refresh_token=token.token_secret,
                token_uri='https://oauth2.googleapis.com/token',
                client_id=settings.GOOGLE_CLIENT_ID,
                client_secret=settings.GOOGLE_CLIENT_SECRET,
                scopes=['https://www.googleapis.com/auth/calendar']
            )

            service = build('calendar', 'v3', credentials=credentials)
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            return JsonResponse({"message": "Event deleted"})

        except Exception as e:
            print("❌ Failed to delete event:", e)
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=400)



def index(request):
    events = []
    all_calendars = []

    if request.user.is_authenticated:
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
                scopes=['https://www.googleapis.com/auth/calendar']
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
                        'location': event.get('location', ''),
                        'description': event.get('description', ''),
                        'creator': event.get('creator', {}).get('email', ''),
                        'calendarId': calendar_id,
                        'backgroundColor': calendar_entry.get('backgroundColor', '#3788d8'),
                        'htmlLink': event.get('htmlLink', ''),
                        'googleEventId': event.get('id'),
                    })


        except Exception as e:
            print("❌ Error fetching calendar data:", e)
            print("Session keys:", request.session.keys())


    return render(request, 'home/index.html', {
        'events': events,
        'calendars': all_calendars
    })