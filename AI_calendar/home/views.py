from django.shortcuts import render
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from django.conf import settings
from allauth.socialaccount.models import SocialToken, SocialAccount
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import json
import datetime
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
import PyPDF2
from io import BytesIO
from django.views.decorators.http import require_GET



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

        title = event_data.get("title")
        start = event_data.get("start")
        end = event_data.get("end")
        location = event_data.get("location")
        description = event_data.get("description")

        if not (title and start and end):
            return JsonResponse({"error": "Missing required fields (title, start, end)"}, status=400)

        event = {
            'summary': title,
            'location': location,
            'description': description,
            'start': {
                'dateTime': start,
                'timeZone': 'America/New_York',
            },
            'end': {
                'dateTime': end,
                'timeZone': 'America/New_York',
            },
            'reminders': {
                'useDefault': True,
            },
        }

        try:
            print("🚨 Sending event to Google Calendar:", json.dumps(event, indent=2))
            created_event = service.events().insert(calendarId='primary', body=event).execute()

            # Fetch back the full event to confirm saved values
            fetched_event = service.events().get(calendarId='primary', eventId=created_event['id']).execute()
            print("✅ Event confirmed in Google Calendar:", json.dumps(fetched_event, indent=2))

            return JsonResponse({
                "message": "Event added to Google Calendar",
                "eventId": created_event["id"],
                "link": created_event.get("htmlLink")
            })

        except Exception as e:
            print("❌ Failed to create event:", e)
            return JsonResponse({"error": str(e)}, status=500)

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
        try:
            print("🔍 Checking Google account and tokens for:", request.user.email)
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
                    timeMin=(datetime.datetime.utcnow() - datetime.timedelta(minutes=5)).isoformat() + 'Z',
                    maxResults=100,
                    singleEvents=True,
                    orderBy='startTime'
                ).execute()

                for event in result.get('items', []):
                    start = event.get('start', {}).get('dateTime') or event.get('start', {}).get('date')
                    end = event.get('end', {}).get('dateTime') or event.get('end', {}).get('date')

                    if not start or not end:
                        continue

                    events.append({
                        'summary': event.get('summary', 'No Title'),
                        'start': start,
                        'end': end,
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

    return render(request, 'home/index.html', {
        'events': events,
        'calendars': all_calendars,
        'chat_history': request.session.get("chat_history", [])
    })


def about(request):
    template_data = {}
    template_data['title'] = 'About'
    return render(request, 'home/about.html', {'template_data': template_data})

def plus(request):
    template_data = {}
    template_data['title'] = 'Plus'
    return render(request, 'home/plus.html', {'template_data': template_data})

@csrf_exempt
@require_POST
@login_required
def ai_process_query(request):
    print("🚀 ai_process_query view triggered")
    user = request.user

    if not SocialToken.objects.filter(account__user=user, account__provider='google').exists():
        return JsonResponse({"error": "Only Google-authenticated users can use this feature."}, status=403)

    query = request.POST.get("query", "").strip()
    uploaded_file = request.FILES.get("file")
    session_history = request.session.get("chat_history", [])
    extracted_text = ""

    if uploaded_file and uploaded_file.name.endswith('.pdf'):
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(uploaded_file.read()))
            for page in pdf_reader.pages:
                extracted_text += page.extract_text() or ""
        except Exception as e:
            return JsonResponse({"error": f"PDF read error: {str(e)}"}, status=400)

    # Add to session history immediately
    session_history.append({
        "query": query,
        "file_text": extracted_text,
        "suggested_events": []  # placeholder until events are ready
    })

    request.session["chat_history"] = session_history
    request.session["event_suggestions"] = []
    request.session["llm_processing"] = True
    request.session.modified = True  # ensure session is saved

    # Kick off background thread
    def simulate_llm_generation(session_key):
        print("🧵 simulate_llm_generation started")
        
        import time
        from django.contrib.sessions.models import Session
        from django.contrib.sessions.backends.db import SessionStore

        time.sleep(30)  # simulate delay

        generated_events = [
            {
                "title": "Generated Event 1",
                "start": "2025-04-22T12:00:00",
                "end": "2025-04-22T13:00:00",
                "location": "Library",
                "description": "AI generated"
            }
        ]

        normalized = [{
            "title": ev["title"],
            "start": ev["start"],
            "end": ev["end"],
            "location": ev.get("location", ""),
            "description": ev.get("description", ""),
            "backgroundColor": "#3788d8",
            "calendarId": "primary",
            "extendedProps": {
                "location": ev.get("location", ""),
                "description": ev.get("description", ""),
                "creator": "",
                "htmlLink": "",
                "googleEventId": ""
            }
        } for ev in generated_events]

        session = SessionStore(session_key=session_key)
        session["event_suggestions"] = normalized
        session["llm_processing"] = False

        # Also update chat history with real suggestions
        history = session.get("chat_history", [])
        if history:
            history[-1]["suggested_events"] = normalized
        session["chat_history"] = history

        session.save()

    from threading import Thread
    Thread(target=simulate_llm_generation, args=(request.session.session_key,)).start()

    return JsonResponse({
        "message": "Query received. LLM processing started.",
        "query": query,
        "processing": True,
        "suggested_events": []
    })


@require_GET
@login_required
def get_chat_history(request):
    return JsonResponse({
        "history": request.session.get("chat_history", [])
    })

@require_GET
@login_required
def get_event_suggestions(request):
    print("📤 Returning suggested events:", request.session.get("event_suggestions", []))
    return JsonResponse({
        "suggested_events": request.session.get("event_suggestions", [])
    })



@require_GET
@login_required
def poll_llm_status(request):
    print("📡 poll_llm_status hit at", datetime.datetime.now().time(), "processing =", request.session.get("llm_processing", False))
    return JsonResponse({
        "processing": request.session.get("llm_processing", False),
        "suggested_events": request.session.get("event_suggestions", [])
    })

