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
import os
from dotenv import load_dotenv

load_dotenv()



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
            print("Sending event to Google Calendar:", json.dumps(event, indent=2))
            created_event = service.events().insert(calendarId='primary', body=event).execute()

            # Fetch back the full event to confirm saved values
            fetched_event = service.events().get(calendarId='primary', eventId=created_event['id']).execute()
            print("Event confirmed in Google Calendar:", json.dumps(fetched_event, indent=2))

            return JsonResponse({
                "message": "Event added to Google Calendar",
                "eventId": created_event["id"],
                "link": created_event.get("htmlLink")
            })

        except Exception as e:
            print("Failed to create event:", e)
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
            print("Failed to delete event:", e)
            return JsonResponse({"error": str(e)}, status=500)

    return JsonResponse({"error": "Invalid request method"}, status=400)


def index(request):
    events = []
    all_calendars = []

    if request.user.is_authenticated:
        try:
            print("Checking Google account and tokens for:", request.user.email)
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
            print("Error fetching calendar data:", e)

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

def contact(request):
    template_data = {}
    template_data['title'] = 'Contact'
    return render(request, 'home/contact.html', {'template_data' : template_data})

def tutorial(request):
    template_data = {}
    template_data['title'] = 'Tutorial'
    return render(request, 'home/tutorial.html', {'template_data' : template_data})    

@csrf_exempt
@require_POST
def ai_process_query(request):
    print("ai_process_query view triggered")
    user = "auth" if request.user.is_authenticated else "guest"
    prefix = f"{user}_"
    #user = request.user

    #if not SocialToken.objects.filter(account__user=user, account__provider='google').exists():
        #return JsonResponse({"error": "Only Google-authenticated users can use this feature."}, status=403)

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

    session_history.append({
        "query": query,
        "file_text": extracted_text,
        "suggested_events": []  
    })

    request.session["chat_history"] = session_history
    request.session["event_suggestions"] = []
    request.session["llm_processing"] = True
    request.session.modified = True  # ensure session is saved

    def simulate_llm_generation(session_key, query, extracted_text=""):
        print("simulate_llm_generation using EventExtraction class")

        from django.contrib.sessions.backends.db import SessionStore
        from home.llm.event_llm import EventExtraction  # path based on your file location

        try:
            extractor = EventExtraction()
            instruction = query if query else None
            events = extractor.extract(instruction, extracted_text)

            normalized = []
            for ev in events:
                normalized.append({
                    "title": ev["title"],
                    "start": ev["start"],
                    "end": ev["end"],
                    "location": ev["location"],
                    "description": ev["description"],
                    "backgroundColor": "#3788d8",
                    "calendarId": "primary",
                    "extendedProps": {
                        "location": ev["location"],
                        "description": ev["description"],
                        "creator": "",
                        "htmlLink": "",
                        "googleEventId": ""
                    }
                })

            session = SessionStore(session_key=session_key)
            session["event_suggestions"] = normalized
            session["llm_processing"] = False

            history = session.get("chat_history", [])
            if history:
                history[-1]["suggested_events"] = normalized
            session["chat_history"] = history
            session.save()

            print(" Events saved to session")

        except Exception as e:
            print(" simulate_llm_generation failed:", str(e))
            session = SessionStore(session_key=session_key)
            session["event_suggestions"] = []
            session["llm_processing"] = False
            session.save()




    from threading import Thread
    Thread(target=simulate_llm_generation, args=(request.session.session_key, query, extracted_text)).start()
    print("ai_process_query view completed, LLM processing started in background.")

    return JsonResponse({
        "message": "Query received. LLM processing started.",
        "query": query,
        "processing": True,
        "suggested_events": []
    })

@csrf_exempt
@require_GET
def get_chat_history(request):
    user = "auth" if request.user.is_authenticated else "guest"
    key = f"{user}_chat_history"
    return JsonResponse({
        "history": request.session.get("chat_history", [])
    })

@csrf_exempt
@require_GET
def get_event_suggestions(request):
    user = "auth" if request.user.is_authenticated else "guest"
    key = f"{user}_chat_history"
    print("Returning suggested events:", request.session.get("event_suggestions", []))
    return JsonResponse({
        "suggested_events": request.session.get("event_suggestions", [])
    })



@csrf_exempt
@require_GET
def poll_llm_status(request):
    user = "auth" if request.user.is_authenticated else "guest"
    key_processing = f"{user}_llm_processing"
    key_suggestions = f"{user}_event_suggestions"    
    print("poll_llm_status hit at", datetime.datetime.now().time(), "processing =", request.session.get("llm_processing", False))
    return JsonResponse({
        "processing": request.session.get("llm_processing", False),
        "suggested_events": request.session.get("event_suggestions", [])
    })
    
@csrf_exempt
@require_POST
def guest_ai_query(request):
    print("📩 Guest AI Query triggered")

    query = request.POST.get("query", "").strip()
    uploaded_file = request.FILES.get("file")
    extracted_text = ""

    if not query and not uploaded_file:
        return JsonResponse({"error": "Query or file required."}, status=400)

    # Extract text from PDF file if present
    if uploaded_file and uploaded_file.name.endswith('.pdf'):
        try:
            pdf_reader = PyPDF2.PdfReader(BytesIO(uploaded_file.read()))
            for page in pdf_reader.pages:
                text = page.extract_text()
                if text:
                    extracted_text += text
        except Exception as e:
            print("PDF read error:", e)
            return JsonResponse({"error": f"PDF read error: {str(e)}"}, status=400)

    try:
        from home.llm.event_llm import EventExtraction
        extractor = EventExtraction()

        instruction = query if query else None
        print(f"Extracting events with query='{instruction}' and PDF content length={len(extracted_text)}")
        events = extractor.extract(instruction, extracted_text)

        if not isinstance(events, list):
            raise ValueError("LLM did not return a list of events")

        normalized = []
        for ev in events:
            normalized.append({
                "title": ev.get("title", "Untitled"),
                "start": ev.get("start", ""),
                "end": ev.get("end", ""),
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
            })

        print(f"{len(normalized)} events extracted.")
        request.session.modified = True
        return JsonResponse({"events": normalized})

    except Exception as e:
        print("Guest LLM extraction failed:", e)
        return JsonResponse({"error": str(e)}, status=500)
